import sys, traceback, subprocess
from pathlib import Path
from PIL import Image
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

v2 = namedtuple("v2", ["x", "y"])
v4 = namedtuple("v4", ["left", "top", "right", "bottom"])
Rectangle = namedtuple("Rectangle", ["x", "y", "width", "height"])
MINAREA = "min_area"

padding = 2
border = 2
output_format = "bc7"


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

        min_rectangle = rectangles[-1]

        for rect_id, w, h in rectangles:
            rect = in_free_rect = free_rect_idx = None

            d = self.find_position(w, h, min_rectangle)

            if d:
                rect, in_free_rect, free_rect_idx = d

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


class CreateAtlas:
    def __init__(self, images, atlas_name):
        self.images = images
        self.atlas_name = atlas_name
        self.is_several_atlas = False
        self.results = []

    def create_atlas(self, rectangles, idx=1):
        # 计算最优图集尺寸
        atlas_size, remaining_rect = self.calculate_optimal_size(rectangles, idx)

        self.maxrects_packing(rectangles, atlas_size, idx)

        if self.is_several_atlas:
            self.is_several_atlas = False

            self.create_atlas(remaining_rect, idx + 1)

        self.write_texture_atlas()

    def maxrects_packing(self, rectangles, atlas_size, idx):
        """使用MaxRects算法进行排列"""
        packer = TexturePacker(atlas_size[0], atlas_size[1])

        results = packer.fit(rectangles)

        # 转换为实际位置
        for rect_id, rect in results:
            self.images[rect_id]["pos"] = v2(rect.x, rect.y)

        self.results.append(
            {
                "name": self.atlas_name + f"-{idx}",
                "rectangles_id": sorted([rect[0] for rect in results]),
                "atlas_size": atlas_size,
            }
        )

    def calculate_optimal_size(self, rectangles, idx):
        """计算最优的图集尺寸"""
        remaining_rect = None

        # 尝试不同的尺寸
        best_size = None

        sizes = [512, 1024, 2048, 4096]

        for i, size in enumerate(sizes):
            efficiency, remaining_rect = self.simulate_packing_efficiency(
                rectangles, size, size
            )

            if size > 1024 and 0.2 < efficiency < 0.45:
                print(f"{size}x{size} 图集利用率较低，启用多图集打包")

                best_size = (sizes[i - 1], sizes[i - 1])
                self.is_several_atlas = True

                efficiency, remaining_rect = self.simulate_packing_efficiency(
                    rectangles, sizes[i - 1], sizes[i - 1]
                )

                break

            elif efficiency > 0.2:  # 至少20%利用率
                best_size = (size, size)

                break

        if best_size:
            print(f"自动计算图集{idx}尺寸: {best_size[0]}x{best_size[1]}")

        return best_size, remaining_rect

    def simulate_packing_efficiency(self, rectangles, width, height):
        """模拟排列并计算空间利用率"""
        packer = TexturePacker(width, height)

        results = packer.fit(rectangles)

        if len(results) < len(rectangles):
            remaining_rect = [
                rect for rect in rectangles if rect[0] not in [r[0] for r in results]
            ]

            return 0, remaining_rect

        used_area = sum(img["width"] * img["height"] for img in self.images)
        total_area = width * height

        return used_area / total_area, []

    def save_to_dds(self, output_file, bc):
        print(f"保存为DDS BC{bc}格式: {output_file}...")

        output_format = f"BC{bc}_UNORM"

        subprocess.run(
            [
                "texconv.exe",
                "-f",
                output_format,  # BC3 格式
                "-y",  # 覆盖已存在文件
                "-o",
                str(output_path),
                output_file,
            ],
            capture_output=True,
            text=True,
        )

        Path(output_file).unlink()

    def write_texture_atlas(self):
        for result in self.results:
            self.write_atlas(result["name"], result)

        self.write_lua_data()

    def write_atlas(self, filename, result):
        # 创建图集
        with Image.new(
            "RGBA", (result["atlas_size"][0], result["atlas_size"][1]), (0, 0, 0, 0)
        ) as atlas:
            output_file = output_path / filename

            for img_id in result["rectangles_id"]:
                img_info = self.images[img_id]
                img_pos = img_info["pos"]

                if len(img_pos) > 0:
                    position = (img_pos.x, img_pos.y)

                    atlas.paste(img_info["image"], position)

            output_file = str(output_file) + ".png"
            atlas.save(output_file)

            # if output_format == "bc7":
            #     self.save_to_dds(output_file, 7)
            # elif output_path == "bc3":
            #     self.save_to_dds(output_file, 3)

    def write_lua_data(self):
        filepath = output_path / f"{self.atlas_name}.lua"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("return {\n")

            for result in self.results:
                for idx, img_id in enumerate(result["rectangles_id"]):
                    img = self.images[img_id]
                    pos = img["pos"]
                    trim = img["trim"]

                    if is_simple_key(img["name"]):
                        f.write(f"\t{img["name"]} = {{\n")
                    else:
                        f.write(f'\t["{img["name"]}"] = {{\n')
                    f.write(f'\t\ta_name = "{result["name"]}.dds",\n')

                    f.write(f"\t\tsize = {{\n")
                    f.write(f"\t\t\t{img["origin_width"]},\n")
                    f.write(f"\t\t\t{img["origin_height"]}\n")
                    f.write(f"\t\t}},\n")

                    f.write(f"\t\ttrim = {{\n")
                    f.write(f"\t\t\t{trim.left},\n")
                    f.write(f"\t\t\t{trim.top},\n")
                    f.write(f"\t\t\t{trim.right},\n")
                    f.write(f"\t\t\t{trim.bottom}\n")
                    f.write(f"\t\t}},\n")

                    f.write(f"\t\ta_size = {{\n")
                    f.write(f"\t\t\t{result["atlas_size"][0]},\n")
                    f.write(f"\t\t\t{result["atlas_size"][1]}\n")
                    f.write(f"\t\t}},\n")

                    f.write(f"\t\tf_quad = {{\n")
                    f.write(f"\t\t\t{pos.x},\n")
                    f.write(f"\t\t\t{pos.y},\n")
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

                    if idx == len(result["rectangles_id"]) - 1:
                        f.write(f"\t}}\n")
                    else:
                        f.write(f"\t}},\n")

            f.write("}")


def process_img(img, last_img_data):
    origin_width = img.width
    origin_height = img.height

    alpha = img.getchannel("A")

    # 获取非透明区域的边界框
    bbox = alpha.getbbox()
    left, top = bbox[0], bbox[1]

    new_img = img.crop(bbox)

    new_width = new_img.width
    new_height = new_img.height

    # if last_img_data:
    #     last_width = last_img_data["width"]
    #     last_height = last_img_data["height"]
    #     last_trim = last_img_data["trim"]

    #     offset_left = (last_width - new_width) - (last_trim.left - left)
    #     offset_top = (last_height - new_height) - (last_trim.top - top)

    #     if abs(offset_left) == 1:
    #         left += offset_left
    #     if abs(offset_top) == 1:
    #         top += offset_top

    right_cropped = origin_width - (left + new_width)
    bottom_cropped = origin_height - (top + new_height)

    trim_data = v4(int(left), int(top), int(right_cropped), int(bottom_cropped))

    return new_img, trim_data


def get_input_subdir():
    last_img_data = None

    input_subdir = {}

    try:
        for dir in input_path.iterdir():
            hash_groups = {}

            input_subdir[dir.name] = {"images": [], "rectangles": []}
            images = input_subdir[dir.name]["images"]

            for image_file in Path(dir).iterdir():
                image_file_name = image_file.stem

                with Image.open(image_file) as img:
                    hash_key = hashlib.md5(img.tobytes()).hexdigest()

                    if hash_key in hash_groups:
                        hash_group = hash_groups[hash_key]
                        hash_group["similar"].append(image_file_name)

                        print(
                            f"跳过加载与 {hash_group["main"]["name"]} 相同的 {image_file_name}"
                        )

                        continue

                    new_img, trim = process_img(img, last_img_data)

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
                        "trim": trim,
                    }

                    images.append(img_data)

                    if hash_key not in hash_groups:
                        hash_groups[hash_key] = {
                            "main": img_data,
                            "similar": img_data["samed_img"],
                        }

                    print(
                        f"加载: {image_file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                    )

                # 准备矩形数据 (id, width, height)
                rectangles = [
                    (i, img["width"] + padding, img["height"] + padding)
                    for i, img in enumerate(images)
                ]

                input_subdir[dir.name]["rectangles"] = sorted(
                    rectangles, key=lambda r: r[1] * r[2], reverse=True
                )

    except Exception as e:
        print(f"加载图片时出错: {e}")
        traceback.print_exc()
        return

    return input_subdir


def main():
    input_subdir = get_input_subdir()

    if input_subdir:
        for atlas_name, subdir in input_subdir.items():
            images = subdir["images"]
            rectangles = subdir["rectangles"]

            create_texture_atlas = CreateAtlas(images, atlas_name.split("-")[0])

            create_texture_atlas.create_atlas(rectangles)

            for img_info in images:
                img_info["image"].close()


if __name__ == "__main__":
    # try:
    main()
    # except Exception as e:
    #     print(f"错误: {e}")
    #     traceback.print_exc()

    input("程序执行完毕，按回车键退出...")
