import sys
import argparse
from pathlib import Path
from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color
import math
from collections import namedtuple
import random


# 添加上级目录到Python路径，以便导入自定义库
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from lib import lib

# 获取基础目录、输入路径和输出路径
base_dir, input_path, output_path = lib.find_and_create_directory(__file__)

def main():
    for image_file in Path(input_path).iterdir():
        with Image(filename=image_file) as img:
            new_img = img.clone()

            with Image(width=img.width, height=img.height, background="transparent") as atlas:
                --atlas.composite(img, 0, 0)

                print(new_img.page)
                new_img.trim()
                print(new_img.page)

                atlas.composite(new_img, 0, 0)

                output_dds = output_path + "/" + image_file.name + ".png"

                # 保存为DDS BC3格式
                print(f"保存为DDS BC3格式: {output_dds}")
                atlas.format = "png"
                atlas.save(filename=output_dds)

                print("图集创建成功!")


if __name__ == "__main__":
    main()

    input("程序执行完毕，按回车键退出...")
