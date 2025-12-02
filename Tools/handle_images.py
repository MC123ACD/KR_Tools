import traceback, config, subprocess
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import utils as U

setting = config.setting["handle_images"]

def load_input_files():
    input_subdir = {"imgs": []}

    for item in config.input_path.iterdir():
        print(f"📖 读取: {item.name}")

        if item.is_dir():
            input_subdir[item.name] = []

            for file in item.iterdir():
                new_img = load_image(file)

                input_subdir[item.name].append(
                    {"name": file.name, "image": new_img, "in_dir": item.name}
                )

        elif item.suffix == ".png":
            new_img = load_image(item)

            input_subdir["imgs"].append(
                {"name": item.name, "image": new_img, "in_dir": False}
            )

    return input_subdir

def load_image(file):
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
            print(f"📖 加载图片  {file.name} ({img.width}x{img.height})")

    return new_img

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
        output_dir = config.output_path / in_dir

        output_dir.mkdir(exist_ok=True)

        output_img = output_dir / name
    else:
        output_img = config.output_path / name

    img.save(output_img)
    if setting["output_format"] == "bc3":
        save_to_dds(output_img, 3)
    elif setting["output_format"] == "bc7":
        save_to_dds(output_img, 7)
    elif setting["output_format"] == "png":
        print(f"✅ 保存为png: {output_img.name}...")

    print(f"🖼️ 保存图片: {name}")

def save_to_dds(output_file, bc):
    """
    将PNG图片转换为DDS格式

    Args:
        output_file: 输出文件路径
        bc: BC压缩格式 (1-7)
    """
    print(f"✅ 保存为DDS BC{bc}格式: {output_file}...")

    output_format = f"BC{bc}_UNORM"

    # 使用texconv工具进行格式转换
    subprocess.run(
        [
            "texconv.exe",
            "-f",
            output_format,  # BC格式
            "-y",  # 覆盖已存在文件
            "-o",
            str(config.output_path),
            str(output_file),
        ],
        capture_output=True,
        text=True,
    )

    # 删除临时PNG文件
    if setting["delete_temporary_png"]:
        Path(output_file).unlink()

def main():
    input_subdir = load_input_files()

    for dir in input_subdir.values():
        for file_data in dir:
            process_img(file_data)

    U.open_output_dir()
