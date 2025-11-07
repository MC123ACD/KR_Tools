import sys, traceback, subprocess
from pathlib import Path
from wand.image import Image
from wand.color import Color
import math, random, hashlib
from collections import namedtuple


# 添加上级目录到Python路径，以便导入自定义库
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

import lib

is_simple_key = lib.is_simple_key

# 获取基础目录、输入路径和输出路径
base_dir, input_path, output_path = lib.find_and_create_directory(__file__)

# 定义矩形类
Rectangle = namedtuple("Rectangle", ["x", "y", "width", "height"])
MINAREA = "min_area"

padding = 2
border = 2
output_format = "bc7"
shake_offset = 1

class TexturePacker:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.border = border
        self.used_rectangles = []
        self.free_rectangles = [
            Rectangle(border, border, width - border, height - border)
        ]

    def fit(self, rectangles):
        """使用MaxRects算法排列矩形"""
        results = []

        # 按面积从大到小排序
        rectangles_sorted = sorted(rectangles, key=lambda r: r[1] * r[2], reverse=True)

        min_rectangle = rectangles_sorted[-1]

        for rect_id, w, h in rectangles_sorted:
            rect = in_free_rect = free_rect_idx = None

            d = self.find_position(w, h, min_rectangle)

            if d:
                rect, in_free_rect, free_rect_idx = d

            if rect:
                # 分割剩余空间
                self.split_free_rectangle(in_free_rect, rect, free_rect_idx)

                # 合并相邻的空闲区域
                self.free_rectangles = self.merge_free_rectangles(self.free_rectangles)

                self.used_rectangles.append(rect)

                results.append((rect_id, rect))

        return results

    def find_position(self, width, height, min_rectangle):
        new_free_rectangles = []
        best_score = float("inf")
        best_rect = None
        in_free_rect = None
        in_free_rect_idx = None

        for free_rect in self.free_rectangles:
            if (
                free_rect.width < min_rectangle[1]
                or free_rect.height < min_rectangle[2]
            ):
                continue
            elif free_rect.width < width or free_rect.height < height:
                new_free_rectangles.append(free_rect)
                continue

            score = self.calculate_score(free_rect, MINAREA)

            if score < best_score:
                best_score = score
                best_rect = Rectangle(free_rect.x, free_rect.y, width, height)
                in_free_rect = free_rect
                in_free_rect_idx = len(new_free_rectangles)

            if free_rect not in new_free_rectangles:
                new_free_rectangles.append(free_rect)

        self.free_rectangles = new_free_rectangles

        if best_rect:
            return best_rect, in_free_rect, in_free_rect_idx

        return None

    def calculate_score(self, rect, strategy):
        if strategy == MINAREA:
            return rect.width * rect.height

        return 0

    def split_free_rectangle(self, free_rect, used_rect, free_rect_idx):
        """分割空闲区域"""
        right = None
        bottom = None

        # 右侧区域
        if used_rect.x + used_rect.width != free_rect.x + free_rect.width:
            width = free_rect.x + free_rect.width - (used_rect.x + used_rect.width)
            height = free_rect.height

            right = Rectangle(
                x=used_rect.x + used_rect.width,
                y=free_rect.y,
                width=width,
                height=height,
            )

        # 下方区域
        if used_rect.y + used_rect.height != free_rect.y + free_rect.height:
            width = used_rect.width
            height = free_rect.y + free_rect.height - (used_rect.y + used_rect.height)

            bottom = Rectangle(
                x=used_rect.x,
                y=used_rect.y + used_rect.height,
                width=width,
                height=height,
            )

        if right and bottom:
            if right.width * right.height < free_rect.width * bottom.height:
                right, bottom = Rectangle(
                    right.x,
                    right.y,
                    right.width,
                    right.height - (bottom.height),
                ), Rectangle(bottom.x, bottom.y, free_rect.width, bottom.height)

            self.free_rectangles[free_rect_idx] = right

            self.free_rectangles.append(bottom)
        elif right:
            self.free_rectangles[free_rect_idx] = right
        elif bottom:
            self.free_rectangles[free_rect_idx] = bottom

    def merge_free_rectangles(self, rectangles):
        """合并空闲矩形"""
        changed = True

        while changed and len(rectangles) > 1:
            changed = False
            rectangles.sort(key=lambda r: (r.y, r.x))

            # 使用临时列表记录要删除的索引
            to_remove = []

            i = 0
            while i < len(rectangles):
                if i in to_remove:
                    i += 1
                    continue

                merged = False
                j = i + 1

                while j < len(rectangles):
                    if j in to_remove:
                        j += 1
                        continue

                    merged_rect = self.try_merge_rectangles(
                        rectangles[i], rectangles[j]
                    )

                    if merged_rect:
                        rectangles[i] = merged_rect
                        to_remove.append(j)
                        changed = True
                        merged = True

                    j += 1
                if not merged:
                    i += 1

            # 从后往前删除，避免索引问题
            for index in reversed(to_remove):
                del rectangles[index]

        return rectangles

    def try_merge_rectangles(self, rect1, rect2):
        """尝试合并两个矩形"""
        # 水平合并
        if (
            rect1.y == rect2.y
            and rect1.height == rect2.height
            and rect1.x + rect1.width == rect2.x
        ):
            return Rectangle(rect1.x, rect1.y, rect1.width + rect2.width, rect1.height)

        # 垂直合并
        if (
            rect1.x == rect2.x
            and rect1.width == rect2.width
            and rect1.y + rect1.height == rect2.y
        ):
            return Rectangle(rect1.x, rect1.y, rect1.width, rect1.height + rect2.height)

        return None


def maxrects_packing(images, atlas_width, atlas_height):
    """使用MaxRects算法进行排列"""
    packer = TexturePacker(atlas_width, atlas_height)

    # 准备矩形数据 (id, width, height)
    rectangles = [
        (i, img["width"] + padding, img["height"] + padding)
        for i, img in enumerate(images)
    ]

    results = packer.fit(rectangles)

    # 转换为实际位置
    for rect_id, rect in results:
        images[rect_id]["pos"] = {
            "x": rect.x,
            "y": rect.y,
        }


def calculate_optimal_size(images):
    """计算最优的图集尺寸"""
    is_several_atlas = False

    # 尝试不同的尺寸
    best_size = None
    best_efficiency = 0

    sizes = [512, 1024, 2048, 4096]

    for size in sizes:
        efficiency = simulate_packing_efficiency(images, size, size)

        if efficiency > best_efficiency and efficiency > 0.25:  # 至少25%利用率
            best_efficiency = efficiency
            best_size = (size, size)

            break
        elif size == sizes[-1]:
            if efficiency > 0.8:
                ...
            else:
                print("最大图集大小利用率较低，启用多图集打包")
                is_several_atlas = True

            best_efficiency = efficiency
            best_size = (size, size)

    return best_size, is_several_atlas


def simulate_packing_efficiency(images, width, height):
    """模拟排列并计算空间利用率"""
    packer = TexturePacker(width, height)

    rectangles = [
        (i, img["width"] + padding, img["height"] + padding)
        for i, img in enumerate(images)
    ]

    results = packer.fit(rectangles)

    if len(results) < len(images):
        return 0

    used_area = sum(img["width"] * img["height"] for img in images)
    total_area = width * height

    return used_area / total_area


def make_trim(img, new_img, images, image_file, last_loaded_img):
    new_img.trim()

    # 实际裁剪计算
    origin_width = img.width
    origin_height = img.height
    new_width = new_img.width
    new_height = new_img.height
    new_page = new_img.page

    _, _, offset_x, offset_y = new_page

    left_cropped = offset_x
    top_cropped = offset_y
    right_cropped = origin_width - (offset_x + new_width)
    bottom_cropped = origin_height - (offset_y + new_height)

    # 检查位置是否有偏移，抵消抖动
    if last_loaded_img:
        last_img = last_loaded_img["image"]
        last_img_page = last_img.page
        _, _, last_offset_x, last_offset_y = last_img_page

        if last_offset_x - left_cropped == shake_offset:
            left_cropped += shake_offset
        elif last_offset_x - left_cropped == -shake_offset:
            left_cropped -= shake_offset
        if last_offset_y - top_cropped == shake_offset:
            top_cropped += shake_offset
        elif last_offset_y - top_cropped == -shake_offset:
            top_cropped -= shake_offset

    return {
        "left": left_cropped,
        "top": top_cropped,
        "right": right_cropped,
        "bottom": bottom_cropped,
    }

def get_input_subdir():
    last_loaded_img = None

    input_subdir = {}

    try:
        for dir in input_path.iterdir():
            hash_groups = {}

            input_subdir[dir.name] = []
            images = input_subdir[dir.name]

            for image_file in Path(dir).iterdir():
                image_file_name = image_file.stem

                img = Image(filename=image_file)

                # 创建特征键
                hash_key = hashlib.md5(img.make_blob()).hexdigest()

                if hash_key in hash_groups:
                    hash_group = hash_groups[hash_key]
                    hash_group["similar"].append(image_file_name)

                    print(f"跳过加载与 {hash_group["main"]["name"]} 相同的图像 {image_file_name}")

                    continue

                new_img = img.clone()

                trim = make_trim(img, new_img, images, image_file, last_loaded_img)

                img_data = {
                    "path": image_file,
                    "image": new_img,
                    "width": new_img.width,
                    "height": new_img.height,
                    "origin_width": img.width,
                    "origin_height": img.height,
                    "name": image_file_name,
                    "samed_img": [],
                    "removed": False,
                    "pos": {},
                    "trim": trim,
                }

                images.append(img_data)

                if hash_key not in hash_groups:
                    hash_groups[hash_key] = {
                        "main": img_data,
                        "similar": img_data["samed_img"],
                    }

                last_loaded_img = img_data

                print(
                    f"加载: {image_file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                )

    except Exception as e:
        print(f"加载图片时出错: {e}")
        traceback.print_exc()
        return

    return input_subdir


def save_to_dds_bc7(output_file, atlas):
    print(f"保存为DDS BC7格式: {output_file}...")
    subprocess.run(
        [
            "texconv.exe",
            "-f",
            "BC7_UNORM",  # BC7 格式
            "-y",  # 覆盖已存在文件
            "-o",
            str(output_path),
            output_file,
        ],
        capture_output=True,
        text=True,
    )


def save_to_dds_bc3(output_file, atlas):
    print(f"保存为DDS BC3格式: {output_file}...")
    subprocess.run(
        [
            "texconv.exe",
            "-f",
            "BC3_UNORM",  # BC3 格式
            "-y",  # 覆盖已存在文件
            "-o",
            str(output_path),
            output_file,
        ],
        capture_output=True,
        text=True,
    )


def write_texture_atlas(images, atlas_width, atlas_height, filename):
    # 创建图集
    with Image(
        width=atlas_width, height=atlas_height, background="transparent"
    ) as atlas:
        output_file = output_path / filename

        for img_info in images:
            img_pos = img_info["pos"]

            if len(img_pos) > 0:
                atlas.composite(img_info["image"], left=img_pos["x"], top=img_pos["y"])

        output_file = str(output_file) + ".png"
        atlas.save(filename=output_file)

        if output_format == "bc7":
            save_to_dds_bc7(output_file, atlas)
        elif output_path == "bc3":
            save_to_dds_bc3(output_file, atlas)

def write_lua_data(images, atlas_width, atlas_height, atlas_name):
    filepath = output_path / f"{atlas_name}.lua"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("return {\n")
        for idx, img in enumerate(images):
            pos = img["pos"]
            trim = img["trim"]

            if is_simple_key(img["name"]):
                f.write(f"\t{img["name"]} = {{\n")
            else:
                f.write(f'\t["{img["name"]}"] = {{\n')
            f.write(f'\t\ta_name = "{atlas_name}.dds",\n')

            f.write(f"\t\tsize = {{\n")
            f.write(f"\t\t\t{img["origin_width"]},\n")
            f.write(f"\t\t\t{img["origin_height"]}\n")
            f.write(f"\t\t}},\n")

            f.write(f"\t\ttrim = {{\n")
            f.write(f"\t\t\t{trim["left"]},\n")
            f.write(f"\t\t\t{trim["top"]},\n")
            f.write(f"\t\t\t{trim["right"]},\n")
            f.write(f"\t\t\t{trim["bottom"]}\n")
            f.write(f"\t\t}},\n")

            f.write(f"\t\ta_size = {{\n")
            f.write(f"\t\t\t{atlas_width},\n")
            f.write(f"\t\t\t{atlas_height}\n")
            f.write(f"\t\t}},\n")

            f.write(f"\t\tf_quad = {{\n")
            f.write(f"\t\t\t{pos["x"]},\n")
            f.write(f"\t\t\t{pos["y"]},\n")
            f.write(f"\t\t\t{img["width"]},\n")
            f.write(f"\t\t\t{img["height"]}\n")
            f.write(f"\t\t}},\n")

            if len(img["samed_img"]) > 0:
                f.write(f"\t\talias = {{\n")
                for i, name in enumerate(img["samed_img"]):
                    if i == len(img["samed_img"]) - 1:
                        f.write(f'\t\t\t"{name}"\n')
                    else:
                        f.write(f'\t\t\t"{name}",\n')
                f.write(f"\t\t}}\n")
            else:
                f.write(f"\t\talias = {{}}\n")

            if idx == len(images) - 1:
                f.write(f"\t}}\n")
            else:
                f.write(f"\t}},\n")

        f.write("}")


def main():
    input_subdir = get_input_subdir()

    if input_subdir:
        for atlas_name, images in input_subdir.items():
            # 计算最优图集尺寸
            texture_size, is_several_atlas = calculate_optimal_size(images)
            print(f"自动计算图集尺寸: {texture_size[0]}x{texture_size[1]}")

            atlas_width, atlas_height = texture_size

            maxrects_packing(images, atlas_width, atlas_height)

            try:
                write_texture_atlas(images, atlas_width, atlas_height, atlas_name)

                write_lua_data(images, atlas_width, atlas_height, atlas_name)

            except Exception as e:
                print(f"写入图集时出错: {e}")
                traceback.print_exc()

                return False

            for img_info in images:
                img_info["image"].close()


if __name__ == "__main__":
    main()

    input("程序执行完毕，按回车键退出...")
