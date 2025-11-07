import sys
import argparse
from pathlib import Path
from PIL import Image
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
        if image_file.is_file():
            with Image.open(image_file) as img:
                alpha = img.getchannel("A")

                # 获取非透明区域的边界框
                bbox = alpha.getbbox()
    # output_dds = output_path / f"{image_file.name}.png"

    # img.save(filename=output_dds)


if __name__ == "__main__":
    main()
