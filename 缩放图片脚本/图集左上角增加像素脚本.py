import os, sys
from pathlib import Path
from PIL import Image

# 添加上级目录到Python路径，以便导入自定义库
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from lib import lib

# 获取基础目录、输入路径和输出路径
base_dir, input_path, output_path = lib.find_and_create_directory(__file__)


def add_px_on_images():
    for file in Path(input_path).iterdir():
        with Image.open(Path(file)) as img:
            pixels = img.load()

            for x in range(0, 3):
                for y in range(0, 3):
                    pixels[x, y] = (255, 255, 255, 255)

            # 保存图片
            output_dir = Path(output_path)

            img.save(output_dir / file.name, quality=100, optimize=True)

            print(f"🖼️ 保存图片: {file.name}")

if __name__ == "__main__":
    add_px_on_images()

    input("程序执行完毕，按回车键退出...")
