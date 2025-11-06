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
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

import lib

is_simple_key = lib.is_simple_key


# 获取基础目录、输入路径和输出路径
base_dir, input_path, output_path = lib.find_and_create_directory(__file__)


def main():
    for image_file in input_path.iterdir():
        with Image(filename=image_file) as img:
            img.trim()
            img_border = 3
            new_width = img.width + 2 * img_border
            new_height = img.height + 2 * img_border

            # 扩展画布，图片居中
            img.extent(
                width=new_width,
                height=new_height,
                x=-img_border,
                y=-img_border,
            )

            output_dds = output_path / f"{image_file.name}.png"

            img.save(filename=output_dds)

            print("图集创建成功!")


if __name__ == "__main__":
    main()

    input("程序执行完毕，按回车键退出...")
