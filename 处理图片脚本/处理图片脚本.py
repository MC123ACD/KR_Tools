import os, sys, json, traceback
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance

# 添加上级目录到Python路径，以便导入自定义库
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

import lib

base_dir, input_path, output_path = lib.find_and_create_directory(__file__)

setting_path = current_dir / "setting.json"

with open(setting_path, "r", encoding="utf-8") as f:
    setting = json.load(f)


def get_input_files():
    input_subdir = {"nil": []}

    for dir in input_path.iterdir():
        print(f"📖 读取: {dir.name}")

        if dir.is_dir():
            input_subdir[dir.name] = []

            for file in dir.iterdir():
                with Image.open(file) as img:
                    new_img = img.copy()

                    if setting["use_trim"]:
                        # 获取Alpha通道
                        alpha = img.getchannel("A")

                        # 裁剪图片
                        new_img = img.crop(alpha.getbbox())

                        print(
                        f"📖 加载图片  {file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                    )
                    else:
                        print(
                        f"📖 加载图片  {file.name} ({img.width}x{img.height})"
                    )

                    input_subdir[dir.name].append(
                        {"name": file.name, "image": new_img, "in_dir": dir.name}
                    )

        else:
            with Image.open(dir) as img:
                new_img = img.copy()

                if setting["use_trim"]:
                    # 获取Alpha通道
                    alpha = img.getchannel("A")

                    # 裁剪图片
                    new_img = img.crop(alpha.getbbox())

                    print(
                        f"📖 加载图片  {dir.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                    )
                else:
                    print(
                        f"📖 加载图片  {file.name} ({img.width}x{img.height})"
                    )

                input_subdir["nil"].append({"name": dir.name, "image": img.copy(), "in_dir": None})

    return input_subdir


def set_size_img(img, size):
    width, height = img.size

    new_width = round(width * size)
    new_height = round(height * size)

    new_img = img.resize((new_width, new_height))

    print(
        f"🔎 缩放图片大小{setting["size"]}倍，从{width}x{height}到{new_width}x{new_height}"
    )

    return new_img


def set_sharpen_img(img, percent, radius, threshold):
    """
    锐化
    """
    sharpened = img.filter(ImageFilter.UnsharpMask(radius, percent, threshold))

    print(f"🔼 锐化图片，强度{percent}%，半径{radius}，阈值{threshold}")

    return sharpened


def set_brightness_img(img, brightness_factor):
    """
    亮度
    """
    enhancer = ImageEnhance.Brightness(img)
    compensated = enhancer.enhance(brightness_factor)

    print(f"🔆 修改图片亮度为{brightness_factor}倍")

    return compensated


def process_img(file_data):
    size = setting["size"]
    sharpen_percent = setting["sharpen_percent"]
    sharpen_radius = setting["sharpen_radius"]
    sharpen_threshold = setting["sharpen_threshold"]
    brightness = setting["brightness"]
    img = file_data["image"]
    name = file_data["name"]
    in_dir = file_data["in_dir"]
    output_img = None

    if size:
        img = set_size_img(img, size)
    if sharpen_percent:
        img = set_sharpen_img(img, sharpen_percent, sharpen_radius, sharpen_threshold)
    if brightness:
        img = set_brightness_img(img, brightness)

    if in_dir:
        output_dir = output_path / in_dir

        output_dir.mkdir(exist_ok=True)

        output_img = output_dir / name
    else:
        output_img = output_path / name

    img.save(output_img)

    print(f"🖼️ 保存图片: {name}")


if __name__ == "__main__":
    try:
        input_subdir = get_input_files()

        for dir in input_subdir.values():
            for file_data in dir:
                process_img(file_data)
    except Exception as e:
        print(f"错误: {e}")
        traceback.print_exc()

    input("程序执行完毕，按回车键退出> ")
