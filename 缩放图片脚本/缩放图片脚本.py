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


def resize_images():
    for dir in Path(input_path).iterdir():
        print(f"📖 读取目录: {dir}")

        for file in Path(dir).iterdir():
            # 打开并处理图片
            with Image.open(file) as img:
                width, height = img.size

                new_width = int(width * 0.71)
                new_height = int(height * 0.71)

                # 调整尺寸
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 保存图片
                output_dir = Path(output_path) / dir.name

                output_dir.mkdir(exist_ok=True)

                resized_img.save(output_dir / file.name, quality=100, optimize=True)

                print(f"🖼️ 保存缩放后图片: {file.name}")

if __name__ == "__main__":
    resize_images()

    input("程序执行完毕，按回车键退出...")
