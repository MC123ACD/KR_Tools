import re, traceback, subprocess, math, config
from PIL import Image
from utils import run_decompiler
from plistlib import load as load_plist
from pathlib import Path
import log
from utils import Point, Size, Rectangle, Bounds

log = log.setup_logging(config.log_level, config.log_file)

setting = config.setting["split_atlas"]


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
                    "atlas_size": Size对象,
                    "images_data": {
                        "image_name1": {
                            "spriteSourceSize": Size对象,
                            "spriteSize": Size对象,
                            "textureRect": Rectangle对象,
                            "spriteOffset": Point对象,
                            "textureRotated": bool
                        },
                        ...
                    }
                },
                ...
            }
    """
    # 执行Lua代码获取原始数据
    lua_data = config.lupa.execute(file_content)

    if not lua_data:
        log.warning("⚠️ 空的图集数据")
        return {}

    # 初始化图集字典和名称集合
    atlases = {}
    has_atlas_names = set()

    # 遍历Lua返回的每个图像数据
    for img_name, img_data in lua_data.items():
        # 提取图集基本信息
        atlas_name = img_data["a_name"]
        atlas_size = img_data["a_size"]
        atlas_size = Size(atlas_size[1], atlas_size[2])
        img_box = img_data["f_quad"]
        img_origin_size = img_data["size"]
        img_origin_size = Size(img_origin_size[1], img_origin_size[2])
        trim = img_data["trim"]
        trim = Bounds(trim[1], trim[2], trim[3], trim[4])
        img_offset = Point(0, 0)
        texture_rotated = img_data["texture_rotated"]
        alias = img_data["alias"]

        # 如果图集名称不在集合中，创建新的图集条目
        if atlas_name not in has_atlas_names:
            atlases[atlas_name] = {
                "atlas_size": atlas_size,
                "images_data": {},
            }
            has_atlas_names.add(atlas_name)

        # 提取精灵的位置和尺寸
        img_pos = Point(img_box[1], img_box[2])
        img_size = Size(img_box[3], img_box[4])

        # 计算精灵相对于原始图像的偏移量
        img_offset.x = math.ceil(trim.left - (img_origin_size.w - img_size.w) / 2)
        img_offset.y = math.floor((img_origin_size.h - img_size.h) / 2 - trim.top)

        # 构建单个精灵的数据结构
        image_data = {
            "spriteSourceSize": img_origin_size,  # 原始精灵尺寸
            "spriteSize": img_size,  # 在图集中的尺寸
            "textureRect": Rectangle(
                img_pos.x, img_pos.y, img_size.w, img_size.h
            ),  # 在图集中的矩形区域
            "spriteOffset": img_offset,  # 相对于原始位置的偏移
            "textureRotated": texture_rotated if texture_rotated else False,  # 是否旋转
        }

        # 获取当前图集的图像数据字典
        current_atlas = atlases[atlas_name]["images_data"]

        # 将精灵数据添加到图集中
        current_atlas[img_name] = image_data

        # 处理别名：将别名指向同一个图像数据
        if alias and len(alias) > 0:
            for _, a in alias.items():
                current_atlas[a] = image_data

    return atlases


def indent(level):
    """
    生成指定层级的缩进字符串

    Args:
        level (int): 缩进层级

    Returns:
        str: 对应层级的缩进字符串
    """
    return "\t" * level


def to_xml(value, level):
    """
    递归将Python数据结构转换为XML格式字符串

    支持的数据类型：
    - dict: 转换为<dict>标签
    - bool: 转换为<true/>或<false/>
    - str/Point/Rectangle/Size/Bounds: 转换为<string>标签
    其他类型不处理

    Args:
        value: 要转换的值
        level (int): 当前的XML层级（用于缩进）

    Returns:
        list: 包含XML行的列表
    """
    xml_content = []

    def a(str):
        """内部函数：将字符串添加到XML内容中"""
        if str:
            xml_content.append(str)

    # 处理字典类型
    if isinstance(value, dict):
        a(f"{indent(level)}<dict>")
        for k, v in value.items():
            a(f"{indent(level + 1)}<key>{str(k)}</key>")
            xml_content.extend(to_xml(v, level + 1))
        a(f"{indent(level)}</dict>")
    # 处理布尔类型
    elif isinstance(value, bool):
        a(f"{indent(level)}<{'true' if value else 'false'}/>")
    # 处理字符串和自定义对象类型（转换为字符串）
    elif isinstance(value, (str, Point, Rectangle, Size, Bounds)):
        a(f"{indent(level)}<string>{str(value)}</string>")
    # 处理列表类型
    elif isinstance(value, list):
        a(f"{indent(level)}<array>")
        for v in value:
            xml_content.extend(to_xml(v, level + 1))
        a(f"{indent(level)}</array>")
    # 处理数值类型
    elif isinstance(value, (int, float)):
        a(f"{indent(level)}<real>{str(value)}</real>")

    # 如果没有内容生成，返回空列表
    if not xml_content:
        return []

    return xml_content


def write_plists(lua_data):
    """
    将解析后的图集数据写入.plist文件

    Args:
        lua_data (dict): 由get_lua_data()返回的图集数据

    Returns:
        list: 生成的.plist文件路径列表
    """
    plist_paths = []

    # 为每个图集创建.plist文件
    for atlas_name, atlas_data in lua_data.items():
        content = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            "\t<dict>",
            "\t\t<key>frames</key>",  # 精灵帧数据键
        ]

        # 将图像数据转换为XML格式并添加到内容中
        content.extend(to_xml(atlas_data["images_data"], 2))

        # 添加元数据部分
        content.extend(
            [
                "\t\t<key>metadata</key>",
                "\t\t<dict>",
                "\t\t\t<key>format</key>",
                "\t\t\t<integer>3</integer>",  # Plist格式版本
                "\t\t\t<key>pixelFormat</key>",
                "\t\t\t<string>RGBA8888</string>",  # 像素格式
                "\t\t\t<key>premultiplyAlpha</key>",
                "\t\t\t<false/>",  # 是否预乘alpha
                "\t\t\t<key>realTextureFileName</key>",
                f"\t\t\t<string>{atlas_name}</string>",  # 实际纹理文件名
                "\t\t\t<key>size</key>",
                f"\t\t\t<string>{str(atlas_data['atlas_size'])}</string>",  # 图集尺寸
                "\t\t\t<key>textureFileName</key>",
                f"\t\t\t<string>{atlas_name}</string>",  # 纹理文件名
                "\t\t</dict>",
                "\t</dict>",
                "</plist>",
            ]
        )

        # 将内容列表合并为字符串
        plist_content = "\n".join(content)

        # 生成.plist文件名（移除扩展名后加.plist）
        plist_filename = f"{atlas_name.rsplit('.', 1)[0]}.plist"
        plist_path = config.output_path / plist_filename

        # 写入文件
        with open(plist_path, "w", encoding="utf-8") as plist_file:
            plist_file.write(plist_content)
            log.info(f"✅ 生成Plist: {plist_filename}")

        plist_paths.append(plist_path)

    return plist_paths


def process_lua(item_file):
    """
    处理.lua文件：反编译、解析并生成.plist文件

    Args:
        item_file (Path): .lua文件路径

    Returns:
        list: 生成的.plist文件路径列表
    """
    # 反编译.lua文件
    run_decompiler(item_file, config.input_path)

    # 读取并解析Lua数据
    with open(item_file, "r", encoding="utf-8-sig") as f:
        lua_data = get_lua_data(f.read())

    # 生成.plist文件
    plist_paths = write_plists(lua_data)
    return plist_paths


def get_input_items():
    """
    扫描输入目录，获取所有需要处理的.lua和.plist文件

    Returns:
        list: 需要处理的.plist文件路径列表
    """
    plist_files = []

    # 获取所有.lua和.plist文件
    item_files = list(config.input_path.glob("*.*"))
    item_files = [f for f in item_files if f.suffix in {".lua", ".plist"}]

    # 处理每个文件
    for item_file in item_files:
        if item_file.suffix == ".lua":
            # 处理.lua文件并获取生成的.plist文件
            plist_paths = process_lua(item_file)
            if plist_paths:
                plist_files.extend(plist_paths)
        else:
            # 直接添加.plist文件
            plist_files.append(item_file)

    return plist_files


def gen_png_from_plist(plist_path, plist_data, png_path):
    """
    根据.plist配置从图集大图中提取并生成单个精灵图片

    Args:
        plist_path (Path): .plist文件路径
        plist_data (dict): 已加载的.plist数据
        png_path (Path): 图集大图文件路径

    Process:
        1. 加载图集大图
        2. 遍历.plist中的所有帧配置
        3. 根据配置裁剪、旋转、定位精灵
        4. 保存为单个.png文件
    """
    # 打开图集大图
    atlas_image = Image.open(png_path)

    frames = plist_data["frames"]

    # 处理每个帧（精灵）
    for frame_key in frames:
        frame_data = frames[frame_key]
        framename = frame_key.replace(".png", "")

        # 解析帧数据
        sprite_size = Size(str_format=frame_data["spriteSourceSize"]).to_int()
        # 精灵原始尺寸
        texture_rect = Rectangle(
            str_format=frame_data["textureRect"]
        ).to_int()  # 在图集中的位置和尺寸
        offset = Point(str_format=frame_data["spriteOffset"]).to_int()  # 偏移量
        texture_rotated = frame_data["textureRotated"]  # 是否旋转

        # 计算在图集中的裁剪框
        result_box = Bounds(
            texture_rect.x,
            texture_rect.y,
            texture_rect.x + texture_rect.w,
            texture_rect.y + texture_rect.h,
        ).to_int()

        # 如果精灵在图集中被旋转，调整裁剪框尺寸
        if texture_rotated:
            # 旋转的精灵：交换宽高
            result_box.w = texture_rect.x + texture_rect.h
            result_box.h = texture_rect.y + texture_rect.w

        # 从图集中裁剪精灵区域
        rect_on_big = atlas_image.crop(tuple(result_box))

        # 如果精灵被旋转，执行逆时针90度旋转
        if texture_rotated:
            rect_on_big = rect_on_big.transpose(Image.ROTATE_90)

        # 计算在目标图像中的粘贴位置
        position = Point(
            (sprite_size.w - texture_rect.w) / 2 + offset.x,
            (sprite_size.h - texture_rect.h) / 2 - offset.y,
        ).to_int()

        # 创建目标尺寸的透明背景图像
        result_image = Image.new("RGBA", tuple(sprite_size), (0, 0, 0, 0))
        # 将裁剪的精灵粘贴到正确位置
        result_image.paste(rect_on_big, tuple(position))

        # 创建输出目录（按图集名称分组）
        output_dir = config.output_path / plist_path.stem.split("-")[0]
        output_dir.mkdir(exist_ok=True)

        # 保存精灵图片
        output_file = output_dir / f"{framename}.png"
        result_image.save(output_file)
        log.info(f"🖼️ 生成图像: {output_file.name}")


def main():
    """
    主函数：执行图集拆分流程

    流程：
    1. 获取输入文件（.lua和.plist）
    2. 处理每个.plist文件
    3. 从图集中提取精灵并保存为.png
    4. 清理临时文件（根据设置）
    """
    # 获取所有需要处理的.plist文件
    plist_files = get_input_items()

    # 处理每个.plist文件
    for plist_file in plist_files:
        # 加载.plist文件
        with open(plist_file, "rb") as file:
            plist_data = load_plist(file)

        # 验证.plist文件格式
        if not plist_data.get("metadata"):
            log.warning(f"⚠️ 无效的Plist文件: {plist_file.name}")
            continue

        # 获取图集文件名
        atalas_file_name = plist_data["metadata"]["realTextureFileName"]

        # 检查图集文件是否存在
        atlas_image = config.input_path / atalas_file_name
        if not atlas_image.exists():
            log.warning(f"⚠️ 图集不存在: {atalas_file_name}")
            continue  # 跳过不存在的图集

        # 从图集中提取精灵
        gen_png_from_plist(plist_file, plist_data, atlas_image)
        log.info(f"✅ 图集拆分完毕: {atalas_file_name}\n")

        # 根据设置删除临时.plist文件
        if setting["delete_temporary_plist"]:
            Path(plist_file).unlink()

    log.info("所有图集拆分完毕")
