import os, sys
from pathlib import Path
from wand.image import Image

# 添加上级目录到Python路径，以便导入自定义库
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

import lib

base_dir, input_path, output_path = lib.find_and_create_directory(__file__)


def set_size(img, size):
    width, height = img.size

    new_width = round(width * size)
    new_height = round(height * size)

    img.resize(new_width, new_height, filter="mitchell")


def resize_images(size):
    for dir in input_path.iterdir():
        print(f"📖 读取: {dir.name}")

        if dir.is_dir():
            for file in dir.iterdir():
                # 打开并处理图片
                with Image(filename=file) as img:
                    set_size(img, size)

                    # 保存图片
                    output_dir = output_path / dir.name

                    output_dir.mkdir(exist_ok=True)

                    img.save(filename=output_dir / file.name)

                    print(f"🖼️ 保存缩放后图片: {file.name}")
        else:
            with Image(filename=dir) as img:
                set_size(img, size)

                img.save(filename=output_path / dir.name)

                print(f"🖼️ 保存缩放后图片: {dir.name}")


if __name__ == "__main__":
    try:
        size = float(input("请输入缩放百分比> "))
    except ValueError:
        print("错误，请输入数字")
        size = float(input("请输入缩放百分比> "))

    resize_images(size)

    input("程序执行完毕，按回车键退出> ")
