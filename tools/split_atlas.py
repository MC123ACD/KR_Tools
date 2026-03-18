import re, traceback, subprocess, math
import lib.config as config
from PIL import Image
from plistlib import load as load_plist
from pathlib import Path
import lib.log as log
from lib.classes import Point, Size, Rectangle, Bounds
from lib.utils import run_decompiler, indent

# 设置日志记录，使用配置文件中的日志级别和日志文件路径
log = log.setup_logging()


def get_lua_data(file_content):
    """
    读取并解析Lua格式的图集数据

    该函数执行Lua代码并解析返回的图集数据，将其转换为标准化的字典格式。
    处理包括精灵的位置、大小、偏移、旋转和别名等属性。

    Args:
        file_content (str): Lua文件的内容字符串

    Returns:
        dict: 结构化的图集数据字典，格式为：
            {
                "atlas_name1": {
                    "atlas_size": Size对象,      # 图集总尺寸
                    "images_data": {            # 精灵数据字典
                        "image_name1": {        # 精灵名称作为键
                            "spriteSourceSize": Size对象,    # 原始精灵尺寸（包含透明区域）
                            "spriteSize": Size对象,         # 在图集中的实际尺寸
                            "textureRect": Rectangle对象,   # 在图集中的位置和区域
                            "spriteOffset": Point对象,      # 相对于原始位置的偏移量
                            "textureRotated": bool         # 精灵是否被旋转（90度）
                        },
                        ...
                    }
                },
                ...
            }

    Raises:
        ValueError: 当Lua代码执行失败或数据结构不符合预期时
        KeyError: 当Lua数据中缺少必要的键时
    """
    # 执行Lua代码获取原始数据（假设config.lupa已配置好Lua环境）
    lua_data = config.lupa.execute(file_content)

    if not lua_data:
        log.warning("⚠️ 空的图集数据")
        return {}

    # 初始化图集字典和名称集合（用于快速查找）
    atlases = {}
    has_atlas_names = set()

    # 遍历Lua返回的每个图像数据，每个图像数据对应一个精灵
    for img_name, img_data in lua_data.items():
        # 提取图集基本信息
        atlas_name = img_data["a_name"]  # 图集文件名
        atlas_size = img_data["a_size"]  # 图集总尺寸 [类型, 宽, 高]
        atlas_size = Size(atlas_size[1], atlas_size[2])  # 转换为Size对象
        img_box = img_data["f_quad"]  # 精灵在图集中的位置和尺寸
        img_origin_size = img_data["size"]  # 精灵原始尺寸
        img_origin_size = Size(img_origin_size[1], img_origin_size[2])
        trim = img_data["trim"]  # 修剪信息 [类型, 上, 下, 左, 右]
        trim = Bounds(trim[1], trim[2], trim[3], trim[4])  # 转换为Bounds对象
        img_offset = Point(0, 0)  # 初始化偏移量
        texture_rotated = img_data["texture_rotated"]  # 是否旋转
        alias = img_data["alias"]  # 精灵别名列表

        # 如果图集名称不在集合中，创建新的图集条目
        if atlas_name not in has_atlas_names:
            atlases[atlas_name] = {
                "atlas_size": atlas_size,  # 图集总尺寸
                "images_data": {},  # 初始化空的精灵字典
            }
            has_atlas_names.add(atlas_name)

        # 提取精灵在图集中的位置和尺寸 [类型, x, y, 宽, 高]
        img_pos = Point(img_box[1], img_box[2])
        img_size = Size(img_box[3], img_box[4])

        # 计算精灵相对于原始图像的偏移量（用于恢复原始位置）
        # 偏移量计算公式：水平偏移 = 左修剪 - (原始宽 - 图集宽)/2
        #                垂直偏移 = (原始高 - 图集高)/2 - 上修剪
        img_offset.x = math.ceil(trim.left - (img_origin_size.w - img_size.w) / 2)
        img_offset.y = math.floor((img_origin_size.h - img_size.h) / 2 - trim.top)

        # 构建单个精灵的数据结构（符合Cocos2d plist格式）
        image_data = {
            "spriteSourceSize": img_origin_size,  # 原始精灵尺寸（未修剪的尺寸）
            "spriteSize": img_size,  # 在图集中的实际尺寸
            "textureRect": Rectangle(  # 在图集中的矩形区域
                img_pos.x, img_pos.y, img_size.w, img_size.h
            ),
            "spriteOffset": img_offset,  # 相对于原始位置的偏移
            "textureRotated": texture_rotated if texture_rotated else False,  # 是否旋转
        }

        # 获取当前图集的图像数据字典引用
        current_atlas = atlases[atlas_name]["images_data"]

        # 将精灵数据以原始名称添加到图集中
        current_atlas[img_name] = image_data

        # 处理别名：将别名指向同一个图像数据（实现精灵复用）
        if alias and len(alias) > 0:
            for _, a in alias.items():
                current_atlas[a] = image_data  # 别名指向相同的数据对象

    return atlases


def to_xml(value, level):
    """
    递归将Python数据结构转换为XML格式字符串

    支持的数据类型：
    - dict: 转换为<dict>标签，包含<key>和<value>
    - list: 转换为<array>标签
    - bool: 转换为<true/>或<false/>自闭合标签
    - str: 转换为<string>标签
    - int/float: 转换为<real>标签（Plist中数值类型）
    - Point/Rectangle/Size/Bounds: 转换为<string>标签（调用str()）

    注：Plist格式要求字典必须包含<key>标签，值紧随其后。

    Args:
        value: 要转换的值，支持上述数据类型
        level (int): 当前的XML层级，用于控制缩进

    Returns:
        list: 包含XML行的列表，每行已包含适当的缩进

    Raises:
        TypeError: 当遇到不支持的数据类型时
    """
    xml_content = []

    def a(str):
        """内部函数：将字符串添加到XML内容列表"""
        if str:
            xml_content.append(str)

    # 处理字典类型（对应Plist的<dict>）
    if isinstance(value, dict):
        a(f"{indent(level)}<dict>")
        for k, v in value.items():
            a(f"{indent(level + 1)}<key>{str(k)}</key>")
            xml_content.extend(to_xml(v, level + 1))
        a(f"{indent(level)}</dict>")
    # 处理布尔类型（对应<true/>或<false/>）
    elif isinstance(value, bool):
        a(f"{indent(level)}<{'true' if value else 'false'}/>")
    # 处理字符串和自定义对象类型（转换为字符串）
    elif isinstance(value, (str, Point, Rectangle, Size, Bounds)):
        a(f"{indent(level)}<string>{str(value)}</string>")
    # 处理列表类型（对应<array>）
    elif isinstance(value, list):
        a(f"{indent(level)}<array>")
        for v in value:
            xml_content.extend(to_xml(v, level + 1))
        a(f"{indent(level)}</array>")
    # 处理数值类型（对应<real>，Plist中整数也使用real）
    elif isinstance(value, (int, float)):
        a(f"{indent(level)}<real>{str(value)}</real>")
    # 忽略None值（Plist不支持None/null）
    elif value is None:
        pass
    else:
        log.warning(f"⚠️ 不支持的数据类型: {type(value)}")

    # 如果没有内容生成，返回空列表
    if not xml_content:
        return []

    return xml_content


def write_plists(lua_data):
    """
    将解析后的图集数据写入.plist文件

    每个图集对应一个.plist文件，文件格式符合Cocos2d纹理图集格式。
    Plist文件包含两部分：
    1. frames: 包含所有精灵的详细数据
    2. metadata: 包含图集的元数据（格式、尺寸、文件名等）

    Args:
        lua_data (dict): 由get_lua_data()返回的图集数据字典

    Returns:
        list: 生成的.plist文件路径列表

    Raises:
        IOError: 当文件写入失败时
    """
    plist_paths = []

    # 为每个图集创建.plist文件
    for atlas_name, atlas_data in lua_data.items():
        # 构建Plist XML内容，按照标准格式组织
        content = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            "\t<dict>",
            "\t\t<key>frames</key>",  # 精灵帧数据键
        ]

        # 将图像数据转换为XML格式并添加到内容中
        content.extend(to_xml(atlas_data["images_data"], 2))

        # 添加元数据部分（图集基本信息）
        content.extend(
            [
                "\t\t<key>metadata</key>",
                "\t\t<dict>",
                "\t\t\t<key>format</key>",
                "\t\t\t<integer>3</integer>",  # Plist格式版本（Cocos2d纹理图集格式3）
                "\t\t\t<key>pixelFormat</key>",
                "\t\t\t<string>RGBA8888</string>",  # 像素格式（RGBA各8位）
                "\t\t\t<key>premultiplyAlpha</key>",
                "\t\t\t<false/>",  # 是否预乘Alpha（通常为false）
                "\t\t\t<key>realTextureFileName</key>",
                f"\t\t\t<string>{atlas_name}</string>",  # 实际纹理文件名
                "\t\t\t<key>size</key>",
                f"\t\t\t<string>{str(atlas_data['atlas_size'])}</string>",  # 图集尺寸
                "\t\t\t<key>textureFileName</key>",
                f"\t\t\t<string>{atlas_name}</string>",  # 纹理文件名（通常与实际相同）
                "\t\t</dict>",
                "\t</dict>",
                "</plist>",
            ]
        )

        # 将内容列表合并为字符串，每行以换行符分隔
        plist_content = "\n".join(content)

        # 生成.plist文件名（移除原始扩展名后添加.plist后缀）
        # 例如：atlas.png.lua -> atlas.png -> atlas.plist
        plist_filename = f"{atlas_name.rsplit('.', 1)[0]}.plist"
        plist_path = config.output_path / plist_filename

        # 写入文件，使用UTF-8编码确保字符兼容性
        try:
            with open(plist_path, "w", encoding="utf-8") as plist_file:
                plist_file.write(plist_content)
                log.info(f"✅ 生成Plist: {plist_filename}")
            plist_paths.append(plist_path)
        except IOError as e:
            log.error(f"❌ 写入Plist文件失败: {plist_path} - {str(e)}")
            raise

    return plist_paths


def process_lua(item_file):
    """
    处理.lua文件：反编译、解析并生成.plist文件

    处理流程：
    1. 反编译.lua文件（如果已加密或编译过）
    2. 读取并解析Lua数据
    3. 转换为标准格式并生成.plist文件

    Args:
        item_file (Path): .lua文件路径对象

    Returns:
        list: 生成的.plist文件路径列表

    Raises:
        FileNotFoundError: 当.lua文件不存在时
        ValueError: 当Lua解析失败时
    """
    # 反编译.lua文件（如果需要），确保得到可读的Lua代码
    run_decompiler(item_file, config.input_path)

    # 读取并解析Lua数据
    try:
        with open(item_file, "r", encoding="utf-8-sig") as f:
            lua_data = get_lua_data(f.read())
    except UnicodeDecodeError:
        log.error(f"❌ 文件编码错误: {item_file}")
        return []

    # 如果解析到数据，生成.plist文件
    if lua_data:
        plist_paths = write_plists(lua_data)
        return plist_paths
    else:
        log.warning(f"⚠️ 未解析到有效数据: {item_file}")
        return []


def get_input_items():
    """
    扫描输入目录，获取所有需要处理的.lua和.plist文件

    处理策略：
    1. 查找所有.lua和.plist文件
    2. .lua文件：处理并转换为.plist文件
    3. .plist文件：直接添加到处理列表
    4. 返回所有需要处理的.plist文件路径

    Returns:
        list: 需要处理的.plist文件路径列表

    Note:
        处理后的.plist文件将保存在输出目录中
    """
    plist_files = []

    # 获取所有.lua和.plist文件（不递归搜索子目录）
    item_files = list(config.input_path.glob("*.*"))
    item_files = [f for f in item_files if f.suffix.lower() in {".lua", ".plist"}]

    # 处理每个文件
    for item_file in item_files:
        if item_file.suffix.lower() == ".lua":
            # 处理.lua文件并获取生成的.plist文件
            try:
                plist_paths = process_lua(item_file)
                if plist_paths:
                    plist_files.extend(plist_paths)
            except Exception as e:
                log.error(f"❌ 处理Lua文件失败: {item_file} - {str(e)}")
                traceback.print_exc()
        else:
            # 直接添加.plist文件到处理列表
            plist_files.append(item_file)

    return plist_files


def gen_png_from_plist(plist_path, plist_data, png_path):
    """
    根据.plist配置从图集大图中提取并生成单个精灵图片

    处理流程：
    1. 加载图集大图
    2. 遍历.plist中的所有帧配置
    3. 根据配置裁剪、旋转、定位精灵
    4. 保存为单个.png文件

    Args:
        plist_path (Path): .plist文件路径
        plist_data (dict): 已加载的.plist数据字典
        png_path (Path): 图集大图文件路径

    Raises:
        FileNotFoundError: 当图集文件不存在时
        KeyError: 当.plist数据中缺少必要的键时
        IOError: 当图片保存失败时

    Note:
        输出目录结构：输出路径/图集名称（不含序号）/精灵名称.png
        例如：output/atlas-0.plist -> output/atlas/精灵1.png
    """
    # 打开图集大图，确保使用RGBA模式以支持透明度
    try:
        atlas_image = Image.open(png_path).convert("RGBA")
    except FileNotFoundError:
        log.error(f"❌ 图集文件不存在: {png_path}")
        return

    frames = plist_data.get("frames", {})
    if not frames:
        log.warning(f"⚠️ Plist文件中没有帧数据: {plist_path}")
        return

    # 处理每个帧（精灵）
    for frame_key, frame_data in frames.items():
        # 清理帧名称，移除.png后缀（如果有）
        framename = frame_key.replace(".png", "")

        # 解析帧数据，使用自定义对象包装原始数据
        sprite_size = Size(frame_data["spriteSourceSize"])  # 精灵原始尺寸
        texture_rect = Rectangle(frame_data["textureRect"])  # 在图集中的位置和尺寸
        offset = Point(frame_data["spriteOffset"])  # 偏移量
        texture_rotated = frame_data.get("textureRotated", False)  # 是否旋转

        # 计算在图集中的裁剪框 [left, top, right, bottom]
        result_box = Bounds(
            texture_rect.x,  # 左边界
            texture_rect.y,  # 上边界
            texture_rect.x + texture_rect.w,  # 右边界
            texture_rect.y + texture_rect.h,  # 下边界
        )

        # 如果精灵在图集中被旋转（90度），调整裁剪框尺寸
        if texture_rotated:
            # 旋转的精灵：宽高互换，需要调整裁剪框
            result_box.right = texture_rect.x + texture_rect.h  # 原高度变为宽度
            result_box.bottom = texture_rect.y + texture_rect.w  # 原宽度变为高度

        # 从图集中裁剪精灵区域（使用Pillow的crop方法）
        try:
            rect_on_big = atlas_image.crop(tuple(result_box))
        except ValueError as e:
            log.error(f"❌ 裁剪区域超出图像范围: {result_box} - {str(e)}")
            continue

        # 如果精灵被旋转，执行逆时针90度旋转恢复原始方向
        if texture_rotated:
            rect_on_big = rect_on_big.transpose(Image.ROTATE_90)
            # 注：Cocos2d中使用顺时针旋转，这里使用逆时针旋转恢复

        # 计算在目标图像中的粘贴位置（居中并考虑偏移）
        # 公式：位置 = (原始尺寸 - 图集尺寸)/2 + 偏移量
        position = Point(
            (sprite_size.w - texture_rect.w) / 2 + offset.x,
            (sprite_size.h - texture_rect.h) / 2 - offset.y,  # Y轴方向相反（向下为正）
        ).to_int()  # 转换为整数像素坐标

        # 创建目标尺寸的透明背景图像（RGBA模式）
        result_image = Image.new("RGBA", tuple(sprite_size), (0, 0, 0, 0))

        # 将裁剪的精灵粘贴到正确位置
        # 使用精灵本身作为遮罩，保留透明度
        result_image.paste(rect_on_big, tuple(position), rect_on_big)

        # 创建输出目录（按图集名称分组）
        # 例如：atlas-0.plist -> atlas（移除序号部分）
        atlas_base_name = plist_path.stem.split("-")[0]
        output_dir = config.output_path / atlas_base_name
        output_dir.mkdir(exist_ok=True)  # 确保目录存在

        # 保存精灵图片，使用PNG格式保留透明度
        output_file = output_dir / f"{framename}.png"
        try:
            result_image.save(output_file, "PNG")
            log.info(f"🖼️ 生成图像: {output_file.name}")
        except IOError as e:
            log.error(f"❌ 保存图像失败: {output_file} - {str(e)}")


def main():
    """
    主函数：执行图集拆分流程

    完整处理流程：
    1. 获取输入文件（.lua和.plist）
    2. 处理每个.plist文件（包括从.lua转换来的）
    3. 从图集中提取精灵并保存为.png文件
    4. 清理临时文件（根据配置）

    异常处理：
    - 捕获并记录处理过程中的异常
    - 跳过无法处理的文件，继续处理其他文件
    - 最终汇总处理结果

    Returns:
        bool: 处理是否成功（全部成功返回True，否则False）
    """
    global setting
    setting = config.setting["split_atlas"]
    log.info("=" * 50)
    log.info("开始图集拆分流程")
    log.info(f"输入目录: {config.input_path}")
    log.info(f"输出目录: {config.output_path}")
    log.info("=" * 50)

    success_count = 0
    error_count = 0

    try:
        # 步骤1: 获取所有需要处理的.plist文件
        plist_files = get_input_items()

        if not plist_files:
            log.warning("⚠️ 未找到需要处理的文件")
            return False

        log.info(f"📋 找到 {len(plist_files)} 个Plist文件待处理")

        # 步骤2: 处理每个.plist文件
        for plist_file in plist_files:
            try:
                log.info(f"🔧 处理Plist文件: {plist_file.name}")

                # 加载.plist文件
                with open(plist_file, "rb") as file:
                    plist_data = load_plist(file)

                # 验证.plist文件格式（必须包含metadata部分）
                if not plist_data.get("metadata"):
                    log.warning(f"⚠️ 无效的Plist文件格式，跳过: {plist_file.name}")
                    error_count += 1
                    continue

                # 获取图集文件名（从metadata中）
                atlas_file_name = plist_data["metadata"].get(
                    "realTextureFileName",
                    plist_data["metadata"].get("textureFileName", ""),
                )

                if not atlas_file_name:
                    log.warning(f"⚠️ 无法获取图集文件名，跳过: {plist_file.name}")
                    error_count += 1
                    continue

                # 检查图集文件是否存在
                atlas_image_path = config.input_path / atlas_file_name
                if not atlas_image_path.exists():
                    log.warning(f"⚠️ 图集文件不存在: {atlas_file_name}，跳过")
                    error_count += 1
                    continue

                # 步骤3: 从图集中提取精灵
                gen_png_from_plist(plist_file, plist_data, atlas_image_path)
                success_count += 1
                log.info(f"✅ 图集拆分完毕: {atlas_file_name}\n")

                # 步骤4: 根据设置删除临时.plist文件
                if setting.get("delete_temporary_plist", False):
                    try:
                        plist_file.unlink()
                        log.info(f"🗑️  已删除临时文件: {plist_file.name}")
                    except Exception as e:
                        log.warning(f"⚠️ 删除临时文件失败: {plist_file.name} - {str(e)}")

            except Exception as e:
                log.error(f"❌ 处理失败: {plist_file.name} - {str(e)}")
                error_count += 1
                traceback.print_exc()
                continue  # 继续处理下一个文件

    except Exception as e:
        log.error(f"❌ 处理流程异常: {str(e)}")
        traceback.print_exc()
        return False

    # 输出处理结果汇总
    log.info("=" * 50)
    log.info("图集拆分流程完成")
    log.info(f"✅ 成功处理: {success_count} 个")
    log.info(f"❌ 失败处理: {error_count} 个")
    log.info(f"📁 输出目录: {config.output_path}")
    log.info("=" * 50)

    return error_count == 0  # 全部成功返回True


# 程序入口点
if __name__ == "__main__":
    # 执行主函数并返回退出码
    success = main()
    exit(0 if success else 1)