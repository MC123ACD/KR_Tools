import re, traceback, subprocess, math, config
from PIL import Image
from utils import run_decompiler
from plistlib import load as load_plist
from pathlib import Path
import log
from utils import Point, Size, Rectangle, Bounds

log = log.setup_logging(config.log_level, config.log_file)

setting = config.setting["split_atlas"]


def get_lua_data(file):
    """
    读取图集数据

    Returns:
        dict: 格式化后的图集数据字典
    """
    lua_data = config.lupa.execute(file)

    if not lua_data:
        log.warning("⚠️ 空的图集数据")
        return {}

    # 初始化图集字典和名称列表
    atlases = {}
    has_atlas_names = set()

    # 遍历Lua返回数据
    for img_name, img_data in lua_data.items():
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

        # 如果图集名称不在列表中，添加新图集
        if not atlas_name in has_atlas_names:
            atlases[atlas_name] = {
                "atlas_size": atlas_size,
                "images_data": {},
            }
            has_atlas_names.add(atlas_name)

        # 获取精灵尺寸和源尺寸
        img_pos = Point(img_box[1], img_box[2])
        img_size = Size(img_box[3], img_box[4])

        # 计算偏移量
        img_offset.x = math.ceil(trim.left - (img_origin_size.w - img_size.w) / 2)
        img_offset.y = math.floor((img_origin_size.h - img_size.h) / 2 - trim.top)

        image_data = {
            "spriteSourceSize": img_origin_size,
            "spriteSize": img_size,
            "textureRect": Rectangle(img_pos.x, img_pos.y, img_size.w, img_size.h),
            "spriteOffset": img_offset,
            "textureRotated": texture_rotated if texture_rotated else False,
        }

        current_atlas = atlases[atlas_name]["images_data"]

        # 为每个精灵创建数据条目
        current_atlas[img_name] = image_data

        # 别名处理
        if alias and len(alias) > 0:
            for _, a in alias.items():
                current_atlas[a] = image_data

    return atlases


def indent(l):
    """生成缩进字符串"""
    return "\t" * l


def to_xml(value, level):
    """递归将数据转换为XML格式"""

    xml_content = []

    def a(str):
        if str:
            xml_content.append(str)

    def e(v):
        if v:
            xml_content.extend(v)

    if isinstance(value, dict):
        # 处理字典类型
        a(f"{indent(level)}<dict>")
        for k, v in value.items():
            a(f"{indent(level + 1)}<key>{str(k)}</key>")
            e(to_xml(v, level + 1))
        a(f"{indent(level)}</dict>")
    elif isinstance(value, bool):
        # 处理布尔类型
        a(f"{indent(level)}<{"true" if value else "false"}/>")
    elif isinstance(value, (str, Point, Rectangle, Size, Bounds)):
        # 处理字符串类型
        a(f"{indent(level)}<string>{str(value)}</string>")

    if not xml_content:
        return ""

    return xml_content


def write_plists(lua_data):
    plist_paths = []

    for atlas_name, atlas_data in lua_data.items():
        content = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
            '<plist version="1.0">',
            "\t<dict>",
            "\t\t<key>frames</key>",
        ]

        def a(str):
            content.append(str)

        content.extend(to_xml(atlas_data["images_data"], 2))
        a("\t\t<key>metadata</key>")
        a("\t\t<dict>")
        a("\t\t\t<key>format</key>")
        a("\t\t\t<integer>3</integer>")
        a("\t\t\t<key>pixelFormat</key>")
        a("\t\t\t<string>RGBA8888</string>")
        a("\t\t\t<key>premultiplyAlpha</key>")
        a("\t\t\t<false/>")
        a("\t\t\t<key>realTextureFileName</key>")
        a(f"\t\t\t<string>{atlas_name}</string>")
        a("\t\t\t<key>size</key>")
        a(f"\t\t\t<string>{str(atlas_data["atlas_size"])}</string>")
        a("\t\t\t<key>textureFileName</key>")
        a(f"\t\t\t<string>{atlas_name}</string>")
        a("\t\t</dict>")
        a("\t</dict>")
        a("</plist>")

        plist_content = "\n".join(content)

        plist_filename = f"{atlas_name.rsplit(".", 1)[0]}.plist"
        plist_path = config.output_path / plist_filename
        with open(plist_path, "w", encoding="utf-8") as plist_file:
            plist_file.write(plist_content)
            log.info(f"✅ 生成Plist: {plist_filename}")

        plist_paths.append(plist_path)

    return plist_paths


def process_lua(item_file):
    run_decompiler(item_file, config.input_path)

    with open(item_file, "r", encoding="utf-8-sig") as f:
        lua_data = get_lua_data(f.read())

    plist_paths = write_plists(lua_data)
    return plist_paths


def get_input_items():
    plist_files = []

    item_files = list(config.input_path.glob("*.*"))
    item_files = [f for f in item_files if f.suffix in {".lua", "plist"}]

    for item_file in item_files:
        if item_file.suffix == ".lua":
            plist_paths = process_lua(item_file)

            if plist_paths:
                plist_files.extend(plist_paths)
        else:
            plist_files.append(item_file)

    return plist_files

def gen_png_from_plist(plist_path, plist_data, png_path):
    """
    根据Plist文件和图集生成小图

    Args:
        plist_path: Plist文件路径
        png_path: 图集图片路径
    """
    # 打开图集
    atlas_image = Image.open(png_path)

    frames = plist_data["frames"]

    # 处理每个帧
    for frame_key in frames:
        frame_data = frames[frame_key]
        framename = frame_key.replace(".png", "")

        sprite_size = Size(str_format=frame_data["spriteSourceSize"])
        texture_rect = Rectangle(str_format=frame_data["textureRect"])
        offset = Point(str_format=frame_data["spriteOffset"])
        texture_rotated = frame_data["textureRotated"]

        # 计算裁剪框
        result_box = [
            int(texture_rect.x),
            int(texture_rect.y),
            int(texture_rect.x + texture_rect.w),
            int(texture_rect.y + texture_rect.h),
        ]
        # 处理旋转的纹理
        if texture_rotated:
            # 交换宽高
            result_box[2] = int(texture_rect.x + texture_rect.h)
            result_box[3] = int(texture_rect.y + texture_rect.w)

        # 裁剪图集
        rect_on_big = atlas_image.crop(result_box)

        # 如果需要，旋转裁剪的图像
        if texture_rotated:
            rect_on_big = rect_on_big.transpose(Image.ROTATE_90)

        # 指定粘贴的位置（左上角坐标）
        position = (
            int((sprite_size.w - texture_rect.w) / 2 + offset.x),
            int((sprite_size.h - texture_rect.h) / 2 - offset.y),
        )

        # 创建新图像并粘贴裁剪的图像
        result_image = Image.new("RGBA", [int(s) for s in sprite_size], (0, 0, 0, 0))
        result_image.paste(rect_on_big, position)

        output_dir = config.output_path / plist_path.stem.split("-")[0]

        output_dir.mkdir(exist_ok=True)

        # 保存结果图像
        output_file = output_dir / f"{framename}.png"
        result_image.save(output_file)
        log.info(f"🖼️ 生成图像: {output_file.name}")


def main():
    plist_files = get_input_items()

    for plist_file in plist_files:
        with open(plist_file, "rb") as file:
            plist_data = load_plist(file)

        if not plist_data.get("metadata"):
            log.warning(f"⚠️ 无效的Plist文件: {plist_file.name}")
            continue

        atalas_file_name = plist_data["metadata"]["realTextureFileName"]

        # 处理对应图集
        atlas_image = config.input_path / atalas_file_name
        if not atlas_image.exists():
            log.warning(f"⚠️ 图集不存在: {atalas_file_name}")

        gen_png_from_plist(plist_file, plist_data, atlas_image)
        log.info(f"✅ 图集拆分完毕: {atalas_file_name}\n")

        # if setting["delete_temporary_plist"]:
        #     Path(plist_file).unlink()

    log.info("所有图集拆分完毕")
