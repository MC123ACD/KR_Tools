import re, traceback, plistlib, subprocess, math, config
from PIL import Image
from utils import run_decompiler
from pathlib import Path

setting = config.setting["split_atlas"]


def read_atlases_data(f):
    """
    读取图集数据

    Returns:
        dict: 格式化后的图集数据字典
    """
    lua_data = config.lupa.execute(f.read())

    if not lua_data:
        print("⚠️ 空的图集数据")
        return {}

    def format_point(x, y):
        """格式化点坐标"""
        return f"{{{x}, {y}}}"

    def format_rect(x, y, width, height):
        """格式化矩形区域"""
        return f"{{{format_point(x, y)}, {format_point(width, height)}}}"

    # 初始化图集字典和名称列表
    atlases = {}
    names = []

    # 遍历Lua返回数据
    for k, v in lua_data.items():
        a_name = v["a_name"]
        # 如果图集名称不在列表中，添加新图集
        if not a_name in names:
            names.append(a_name)
            atlases[a_name] = {"size": format_point(v["a_size"][1], v["a_size"][2])}

        atlas = atlases[a_name]

        # 获取精灵尺寸和源尺寸
        spriteWidth, spriteHeight = v["f_quad"][3], v["f_quad"][4]
        spriteSourceWidth, spriteSourceHeight = v["size"][1], v["size"][2]

        # 计算偏移量
        spriteOffsetX = math.ceil(v["trim"][1] - (spriteSourceWidth - spriteWidth) / 2)
        spriteOffsetY = math.floor(
            (spriteSourceHeight - spriteHeight) / 2 - v["trim"][2]
        )

        atlas_data = {
            "spriteOffset": format_point(spriteOffsetX, spriteOffsetY),
            "spriteSize": format_point(spriteWidth, spriteHeight),
            "spriteSourceSize": format_point(spriteSourceWidth, spriteSourceHeight),
            "textureRect": format_rect(
                v["f_quad"][1], v["f_quad"][2], spriteWidth, spriteHeight
            ),
            "textureRotated": v["textureRotated"] if v["textureRotated"] else False,
        }

        # 为每个精灵创建数据条目
        atlas[k + ".png"] = atlas_data

        # 别名处理
        if v["alias"] and len(v["alias"]) > 0:
            for _, alias in v["alias"].items():
                atlas[alias + ".png"] = atlas_data

    return atlases


def to_plist(t, a_name, size):
    """
    将数据转换为Plist格式的XML字符串

    Args:
        t: 图集数据字典
        a_name: 图集名称
        size: 图集尺寸

    Returns:
        str: Plist格式的XML字符串
    """

    def to_xml(t, level):
        """递归将数据转换为XML格式"""

        def indent(l):
            """生成缩进字符串"""
            return "\t" * l

        o = ""
        if isinstance(t, dict):
            # 处理字典类型
            o += f"{indent(level)}<dict>\n"
            for k, v in t.items():
                o += f"{indent(level + 1)}<key>{str(k)}</key>\n"
                o += to_xml(v, level + 1)

            o += f"{indent(level)}</dict>\n"
        elif isinstance(t, list):
            # 处理列表类型
            o += f"{indent(level)}<array>\n"
            for v in t:
                o += to_xml(v, level + 1)
            o += f"{indent(level)}</array>\n"
        elif isinstance(t, bool):
            # 处理布尔类型
            o += f"{indent(level)}<{"true" if t else "false"}/>\n"
        elif isinstance(t, int) or isinstance(t, float):
            # 处理数值类型
            o += f"{indent(level)}<real>{str(t)}</real>\n"
        elif isinstance(t, str):
            # 处理字符串类型
            o += f"{indent(level)}<string>{str(t)}</string>\n"

        return o

    # 返回完整的Plist XML字符串
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
\t<dict>
\t\t<key>frames</key>
{to_xml(t, 2)}
\t\t<key>metadata</key>
\t\t<dict>
\t\t\t<key>format</key>
\t\t\t<integer>3</integer>
\t\t\t<key>pixelFormat</key>
\t\t\t<string>RGBA8888</string>
\t\t\t<key>premultiplyAlpha</key>
\t\t\t<false/>
\t\t\t<key>realTextureFileName</key>
\t\t\t<string>{a_name}</string>
\t\t\t<key>size</key>
\t\t\t<string>{size}</string>
\t\t\t<key>textureFileName</key>
\t\t\t<string>{a_name}</string>
\t\t</dict>
\t</dict>
</plist>"""


def gen_png_from_plist(plist_path, png_path, open_plist=None):
    """
    根据Plist文件和图集生成小图

    Args:
        plist_path: Plist文件路径
        png_path: 图集图片路径
        open_plist: 已打开的Plist数据（可选）
    """
    # 打开图集
    big_image = Image.open(png_path)

    # 读取并解析plist文件
    with open(plist_path, "rb") as file:
        if open_plist:
            root = open_plist
        else:
            root = plistlib.load(file)

        frames = root["frames"]

    # 辅助函数：将字符串转换为整数列表
    def to_int_list(x):
        return list(map(int, x.replace("{", "").replace("}", "").split(",")))

    # 辅助函数：将字符串转换为浮点数列表
    def to_float_list(x):
        return list(map(float, x.replace("{", "").replace("}", "").split(",")))

    # 处理每个帧
    for frame_key in frames:
        frame_data = frames[frame_key]
        framename = frame_key.replace(".png", "")

        # 获取尺寸和位置信息
        sprite_size = to_int_list(frame_data["spriteSourceSize"])
        texture_rect = to_int_list(frame_data["textureRect"])
        offset = to_float_list(frame_data["spriteOffset"])

        # 计算裁剪框
        result_box = texture_rect.copy()
        if frame_data["textureRotated"]:
            # 处理旋转的纹理
            result_box[0] = int(texture_rect[0])
            result_box[1] = int(texture_rect[1])
            # 交换宽高
            result_box[2] = int(texture_rect[0] + texture_rect[3])
            result_box[3] = int(texture_rect[1] + texture_rect[2])
        else:
            # 处理正常纹理
            result_box[0] = int(texture_rect[0])
            result_box[1] = int(texture_rect[1])
            result_box[2] = int(texture_rect[0] + texture_rect[2])
            result_box[3] = int(texture_rect[1] + texture_rect[3])

        # 裁剪图集
        rect_on_big = big_image.crop(result_box)

        # 如果需要，旋转裁剪的图像
        if frame_data["textureRotated"]:
            rect_on_big = rect_on_big.transpose(Image.ROTATE_90)

        # 指定粘贴的位置（左上角坐标）
        position = (
            int((sprite_size[0] - texture_rect[2]) / 2 + offset[0]),
            int((sprite_size[1] - texture_rect[3]) / 2 - offset[1]),
        )

        # 创建新图像并粘贴裁剪的图像
        result_image = Image.new("RGBA", sprite_size, (0, 0, 0, 0))
        result_image.paste(rect_on_big, position)

        output_dir = config.output_path / plist_path.stem.split("-")[0]

        output_dir.mkdir(exist_ok=True)

        # 保存结果图像
        output_file = output_dir / f"{framename}.png"
        result_image.save(output_file)
        print(f"🖼️ 生成图像: {output_file.name}")


def process_plist_conversion():
    """处理Plist文件生成并生成图像"""

    try:
        # 遍历输入目录中的所有文件
        for filename in config.input_path.iterdir():
            if filename.suffix == ".lua":
                # 处理Lua文件
                run_decompiler(filename, config.input_path)

                with open(filename, "r", encoding="utf-8-sig") as f:
                    print(f"📖 读取文件: {filename.name}")

                    # 读取图集数据
                    atlases = read_atlases_data(f)

                    # 处理每个图集
                    for a_name, atlas in atlases.items():
                        size = atlas["size"]
                        del atlas["size"]

                        # 检查文件扩展名
                        match = re.search(r"\.(png|dds)$", a_name)
                        if not match:
                            print(f"⚠️ 跳过无效文件: {a_name}")
                            continue

                        # 生成Plist文件
                        base_name = a_name.rsplit(".", 1)[0]
                        plist_filename = f"{base_name}.plist"
                        plist_path = config.output_path / plist_filename

                        with open(plist_path, "w", encoding="utf-8-sig") as plist_file:
                            plist_file.write(to_plist(atlas, a_name, size))
                            print(f"✅ 生成Plist: {plist_filename}")

                        # 处理对应图集
                        atlas_image = config.input_path / a_name
                        if atlas_image.exists():
                            gen_png_from_plist(plist_path, atlas_image)
                            print(f"✅ 图集拆分完毕: {a_name}\n")

                        else:
                            print(f"⚠️ 图集不存在: {a_name}")

                        if setting["delete_temporary_plist"]:
                            Path(plist_path).unlink()

            elif filename.suffix == ".plist":
                # 处理现有的Plist文件
                print(f"📖 读取文件: {filename.name}")

                with open(filename, "rb") as file:
                    open_plist = plistlib.load(file)

                    if not open_plist.get("metadata") :
                        print(f"⚠️ 无效的Plist文件: {filename.name}")
                        continue

                    frames = open_plist["metadata"]["realTextureFileName"]

                # 处理对应图集
                atlas_image = config.input_path / frames
                if atlas_image.exists():
                    # 生成图像
                    gen_png_from_plist(filename, atlas_image, open_plist)
                    print(f"✅ 图集拆分完毕: {a_name}\n")
                else:
                    print(f"⚠️ 图集不存在: {frames}")

    except Exception as e:
        traceback.print_exc()


def main():
    process_plist_conversion()

    print("所有图集拆分完毕")
