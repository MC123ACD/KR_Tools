import os, sys, json
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
            input_subdir[dir.name] = {}

            for file in dir.iterdir():
                # 打开并处理图片
                img = Image.open(file)
                input_subdir[dir.name].append(
                    {"name": file.name, "image": img, "in_dir": dir.name}
                )
        else:
            img = Image.open(dir)
            input_subdir["nil"].append({"name": dir.name, "image": img, "in_dir": None})

    return input_subdir


def set_size_img(size, file_data):
    name = file_data["name"]
    img = file_data["image"]

    width, height = img.size

    new_width = round(width * size)
    new_height = round(height * size)

    new_img = img.resize((new_width, new_height))

    return new_img


def set_sharpen_img(img, sharpness_params):
    """
    锐化
    """
    # 应用锐化
    sharpened = img.filter(ImageFilter.UnsharpMask(**sharpness_params))

    return sharpened

def set_brightness_img(img, brightness_factor):
    """
    亮度
    """

    # 调整亮度补偿
    enhancer = ImageEnhance.Brightness(img)
    compensated = enhancer.enhance(brightness_factor)

    return compensated

def process_img(file_data):
    size = setting["size"]
    sharpen = setting["sharpen"]
    brightness = setting["brightness"]
    img = file_data["image"]
    name = file_data["name"]
    in_dir = file_data["in_dir"]
    output_img = None

    if size:
        img = set_size_img(size, file_data)
    if sharpen:
        img = set_sharpen_img()
    if brightness:
        img = set_brightness_img()

    if in_dir:
        output_dir = output_path / in_dir

        output_dir.mkdir(exist_ok=True)

        output_img = output_dir / name
    else:
        output_img = output_path / name

    img.save(output_img)

    print(f"🖼️ 保存缩放后图片: {name}")


if __name__ == "__main__":
    input_subdir = get_input_files()

    for dir in input_subdir.values():
        for file_data in dir:
            process_img(file_data)

    input("程序执行完毕，按回车键退出> ")
