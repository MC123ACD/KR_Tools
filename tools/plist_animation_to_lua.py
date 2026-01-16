import re, traceback, plistlib, math
import lib.config as config
from lib.classes import WriteLua
from lib.templates import write_common_animations_data_template, write_exos_animations_data_template
import lib.log as log

# 设置日志记录，使用配置文件中的日志级别和日志文件路径
log = log.setup_logging(config.log_level, config.log_file)


def matrix_to_transform_params(matrix):
    """
    将仿射变换矩阵转换为变换参数
    
    假设变换顺序为：缩放(sx,sy) → 倾斜(k) → 旋转(r) → 平移(tx,ty)
    矩阵形式: [a, b, tx; c, d, ty]
    
    该函数将6个矩阵元素(a,b,c,d,tx,ty)分解为平移、缩放、旋转和倾斜参数

    Args:
        matrix (list): 包含6个元素的仿射变换矩阵列表 [a, b, c, d, tx, ty]

    Returns:
        dict: 包含变换参数的字典，包含以下键：
            - x: X轴平移量
            - y: Y轴平移量
            - sx: X轴缩放因子
            - sy: Y轴缩放因子
            - r: 旋转角度（弧度）
            - kx: X方向倾斜角度（弧度）
            - ky: Y方向倾斜角度（弧度）
    """
    # 提取矩阵元素
    a, b, c, d, tx, ty = matrix

    # 计算平移
    x, y = tx, ty

    # 计算行列式（用于检查是否有反射和奇异矩阵）
    det = a * d - b * c

    # 处理奇异矩阵（行列式接近0的情况）
    if abs(det) < 1e-10:
        # 接近奇异矩阵时使用近似值
        if abs(a) < 1e-10 and abs(d) < 1e-10:
            # 当a和d都接近0时，可能是纯倾斜变换
            sx = math.hypot(b, c)
            sy = 0
            r = 0
            kx = 0
            ky = math.atan2(c, b) if b != 0 else 0
        else:
            # 一般奇异矩阵情况
            sx = math.hypot(a, c)
            sy = math.hypot(b, d)
            r = math.atan2(c, a) if a != 0 else 0
            kx = math.atan2(b, d) if d != 0 else 0
            ky = 0
    else:
        # 正常矩阵情况：去除旋转影响以提取缩放和倾斜
        # 计算旋转角度（atan2返回的是 -π 到 π 之间的值）
        r = math.atan2(b - c, a + d) / 2

        # 计算去除旋转后的矩阵
        cos_r = math.cos(r)
        sin_r = math.sin(r)

        # 构建旋转矩阵的逆
        # 计算 M_rot_inv = [cos(r), sin(r); -sin(r), cos(r)]
        # 然后计算 M_no_rot = M * M_rot_inv
        a_prime = a * cos_r + c * sin_r
        b_prime = b * cos_r + d * sin_r
        c_prime = -a * sin_r + c * cos_r
        d_prime = -b * sin_r + d * cos_r

        # 提取缩放和倾斜
        sx = math.copysign(math.hypot(a_prime, c_prime), det)
        sy = math.copysign(math.hypot(b_prime, d_prime), det)

        # 计算倾斜角度（通常倾斜是相同的，但这里保持kx,ky分离以匹配你的需求）
        # 注意：通常倾斜矩阵是上三角或下三角形式
        if abs(sx) > 1e-10:
            kx = math.atan2(b_prime, sx)
        else:
            kx = 0

        if abs(sy) > 1e-10:
            ky = math.atan2(c_prime, sy)
        else:
            ky = 0

    return {
        "x": x,  # 平移X
        "y": y,  # 平移Y
        "sx": sx,  # 缩放X
        "sy": sy,  # 缩放Y
        "r": r,  # 旋转角度（弧度）
        "kx": kx,  # X方向倾斜角度
        "ky": ky,  # Y方向倾斜角度
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