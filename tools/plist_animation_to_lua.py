import re, traceback, plistlib, math
import lib.config as config
from lib.classes import WriteLua
from lib.templates import write_common_animations_data_template, write_exos_animations_data_template
import lib.log as log

# 设置日志记录，使用配置文件中的日志级别和日志文件路径
log = log.setup_logging()

def matrix_to_transform_params(matrix):
    """
    将仿射变换矩阵转换为变换参数（平移、缩放、水平倾斜、旋转）。
    变换顺序：缩放(sx,sy) → 水平倾斜(kx) → 旋转(r) → 平移(tx,ty)
    垂直倾斜 ky 不需要考虑，固定为 0。

    Args:
        matrix (list): [a, b, c, d, tx, ty]

    Returns:
        dict: {x, y, sx, sy, r, kx, ky}，其中 ky = 0
    """
    a, b, c, d, x, y = matrix
    
    # 计算基础变换参数
    r = math.atan2(b, a)               # 旋转角
    sx = math.hypot(a, b)              # X轴缩放
    sy = math.hypot(c, d)              # Y轴缩放（可能被覆盖）
    test_r = -math.atan2(c, d)           # 测试角
    
    # 根据条件决定是否修正 kx 和 sy
    kx = 0.0
    if not test_r - r < 1e-9 and not math.isclose(sx, 0.0):
        kx = (a * c + b * d) / sx
        sy = (a * d - b * c) / sx

    return {
        "x": x,
        "y": y,
        "sx": sx,
        "sy": sy,
        "r": r,
        "kx": kx,
        "ky": 0.0,      # 固定为 0
    }


def get_animations_data(plist_data):
    """
    从Plist数据中提取动画信息
    
    支持两种类型的动画数据：
    1. 普通动画：基于帧序列的传统动画
    2. 骨骼动画（Exoskeletons）：基于骨骼和部件的复杂动画

    Args:
        plist_data (dict): 从Plist文件加载的数据

    Returns:
        tuple: (动画数据字典, 是否为骨骼动画的布尔值)
    """
    animations = plist_data["animations"]

    if isinstance(animations, dict):
        # 处理普通动画（帧序列动画）
        animations_data = {"animations_data": {}}

        layer_keys = ["layerStart", "layerEnd"]

        for anim_name, anim_data in plist_data["animations"].items():
            # 检查是否是分层动画（layer动画）
            if any(key in anim_data for key in layer_keys):
                # 解析动画名称格式：前缀_动作名
                match = re.match(r"(.+)_(.+)", anim_name)
                prefix, action = match.group(1), match.group(2)

                new_key = f"{prefix}X_{action}"

                if not re.search("layer$", "prefix"):
                    new_key = f"{prefix}_layerX_{action}"

                # 添加分层动画数据
                animations_data["animations_data"][re.sub(r"^Stage_\d+_", "", new_key)] = {
                    "layer_prefix": anim_data["prefix"] + "%i",  # 层名前缀（带占位符）
                    "layer_to": anim_data["layerEnd"],  # 结束层索引
                    "layer_from": anim_data["layerStart"],  # 起始层索引
                    "to": anim_data["toIndex"],  # 结束帧索引
                    "from": anim_data["fromIndex"],  # 起始帧索引
                    "is_layer": True,  # 标记为分层动画
                }
                continue

            # 添加普通动画数据
            animations_data["animations_data"][re.sub(r"^Stage_\d+_", "", anim_name)] = {
                "prefix": anim_data["prefix"],  # 动画帧前缀
                "to": anim_data["toIndex"],  # 结束帧索引
                "from": anim_data["fromIndex"],  # 起始帧索引
                "is_layer": False,  # 标记为非分层动画
            }

        return animations_data, False
    elif isinstance(animations, list):
        # 处理骨骼动画（Exoskeletons）
        exoskeletons_data = {
            "fps": 30,  # 帧率（每秒帧数）
            "partScaleCompensation": plist_data["partScaleCompensation"],  # 部件缩放补偿
            "animations": [],  # 动画列表
            "parts": {},  # 部件字典
        }

        # 处理每个动画
        for anim_data in animations:
            a = {"name": anim_data["name"], "frames": []}

            # 处理动画的每一帧
            for af in anim_data["frames"]:
                f = {
                    "attachPoints": af["attachPoints"],  # 附着点
                    "duration": af["duration"],  # 帧持续时间
                    "events": af["events"],  # 帧事件
                    "parts": [],  # 部件列表
                }

                # 处理帧中的每个部件
                for p in af["parts"]:
                    f["parts"].append(
                        {
                            "alpha": p.get("alpha"),  # 透明度（可选）
                            "name": p["name"],  # 部件名称
                            "xform": matrix_to_transform_params(p["matrix"]),  # 变换矩阵参数
                        }
                    )

                a["frames"].append(f)

            exoskeletons_data["animations"].append(a)

        # 处理所有部件
        for part in plist_data["parts"]:
            name = part["name"]
            exoskeletons_data["parts"][name] = {
                "name": name,
                "offsetX": part["offsetX"],  # X轴偏移
                "offsetY": part["offsetY"],  # Y轴偏移
            }

        return exoskeletons_data, True


def write_common_animations_data(data, filename):
    """
    写入普通动画数据到Lua文件
    
    根据动画类型（是否分层）调整文件名并写入相应的模板

    Args:
        data (dict): 动画数据字典
        filename (str): 原始文件名（不含扩展名）
    """
    is_layer = False

    # 检查是否包含分层动画
    for anim_data in data["animations_data"].values():
        if anim_data["is_layer"]:
            is_layer = True
            break

    # 使用模板渲染Lua内容
    lua_content = write_common_animations_data_template.render(data)
    file = f"{filename}.lua"

    # 如果是分层动画且文件名中不包含"layer_animations"，则修改文件名
    if is_layer and not re.search(r"layer_animations", filename):
        file = file.replace("animations", "layer_animations")

    # 确保输出目录存在
    output_dir = config.output_path / "animations"
    output_dir.mkdir(exist_ok=True)

    log.info(f"写入动画数据{file}...")

    # 写入文件
    with open(output_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def write_exos_data(exos_data, filename):
    """
    写入骨骼动画数据到Lua文件

    Args:
        exos_data (dict): 骨骼动画数据
        filename (str): 原始文件名（不含扩展名）
    """
    # 使用模板渲染Lua内容
    lua_content = write_exos_animations_data_template.render(exos_data)
    file = f"{filename}.lua"

    # 确保输出目录存在
    output_dir = config.output_path / "exoskeletons"
    output_dir.mkdir(exist_ok=True)

    log.info(f"写入骨骼动画数据{file}...")

    # 写入文件
    with open(output_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def get_input_files():
    """
    扫描输入目录，获取所有动画相关的Plist文件

    查找包含"layer_animations"或"animations"的文件名的Plist文件

    Returns:
        list: 文件数据列表，每个元素是(文件名, plist_data)元组
    """
    files = []

    # 扫描输入目录中的所有文件
    for file in config.input_path.iterdir():
        # 匹配文件名中包含"layer_animations"或"animations"的文件
        match = re.search(r"layer_animations|animations", file.stem)
        if not match or not match.group():
            continue

        try:
            # 加载Plist文件
            with open(file, "rb") as f:
                plist_data = plistlib.load(f)

            log.info(f"📖 读取文件: {file.name}")
            file_data = (file.stem, plist_data)

            files.append(file_data)
        except Exception as e:
            log.error(f"❌ 读取文件失败: {file.name} - {str(e)}")

    return files


def main():
    """
    主函数：执行动画数据转换流程

    处理流程：
    1. 获取所有动画相关的Plist文件
    2. 提取动画数据
    3. 根据动画类型写入相应的Lua文件

    Returns:
        bool: 处理是否成功
    """
    files = get_input_files()

    if not files:
        log.warning("⚠️ 未找到动画相关的Plist文件")
        return False

    try:
        success_count = 0
        error_count = 0

        for name, plist_data in files:
            try:
                # 提取动画数据
                ani_data, is_exo = get_animations_data(plist_data)

                # 根据动画类型写入相应的Lua文件
                if is_exo:
                    write_exos_data(ani_data, name)
                else:
                    write_common_animations_data(ani_data, name)

                success_count += 1
                log.info(f"✅ 成功处理: {name}")
            except Exception as e:
                error_count += 1
                log.error(f"❌ 处理失败: {name} - {str(e)}")
                traceback.print_exc()

        # 输出处理结果
        log.info("=" * 50)
        log.info("动画数据转换完成")
        log.info(f"✅ 成功处理: {success_count} 个文件")
        log.info(f"❌ 失败处理: {error_count} 个文件")
        log.info("=" * 50)

        return error_count == 0

    except Exception as e:
        log.error(f"❌ 处理流程异常: {str(e)}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    """
    程序入口点
    执行主函数并根据结果返回退出码
    """
    # 执行主函数
    success = main()
    # 成功返回0，失败返回1
    exit(0 if success else 1)