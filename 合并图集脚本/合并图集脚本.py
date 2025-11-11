import sys, traceback, subprocess
from pathlib import Path
from PIL import Image, ImageDraw
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

# 定义数据结构：
# v2: 二维向量，表示位置坐标 (x, y)
# v4: 四维向量，表示裁剪边界 (left, top, right, bottom)
# Rectangle: 矩形区域，包含位置和尺寸 (x, y, width, height)
v2 = namedtuple("v2", ["x", "y"])
v4 = namedtuple("v4", ["left", "top", "right", "bottom"])
Rectangle = namedtuple("Rectangle", ["x", "y", "width", "height"])
MINAREA = "min_area"  # 最小面积策略标识

# 图集打包参数
padding = 3  # 图片之间的内边距
border = 4  # 图集边界留白
output_format = "png"  # 输出格式
alignment_offset_fix = 1    # 对齐偏移修正
trigger_several_efficiency = 0.45    # 多图集打包时机

class TexturePacker:
    """纹理打包器，使用MaxRects算法进行矩形排列"""

    def __init__(self, width, height):
        """
        初始化打包器

        Args:
            width: 打包区域宽度
            height: 打包区域高度
        """
        self.width = width
        self.height = height
        self.used_rectangles = []  # 已使用的矩形区域列表
        # 初始空闲区域，考虑边界留白
        self.free_rectangles = [
            Rectangle(border, border, width - border, height - border)
        ]

    def fit(self, rectangles):
        """
        使用MaxRects算法排列矩形

        Args:
            rectangles: 待排列的矩形列表，格式为[(id, width, height), ...]

        Returns:
            results: 排列结果列表，格式为[(rect_id, Rectangle), ...]
        """
        results = []

        # 获取最小的矩形（用于优化判断）
        min_rectangle = rectangles[-1]

        # 遍历所有矩形进行排列
        for rect_id, w, h in rectangles:
            rect = in_free_rect = free_rect_idx = None

            # 寻找最佳放置位置
            d = self.find_position(w, h, min_rectangle)

            if d:
                rect, in_free_rect, free_rect_idx = d

                # 分割剩余空间
                self.split_free_rectangle(in_free_rect, rect, free_rect_idx)

                # 合并相邻的空闲区域
                self.free_rectangles = self.merge_free_rectangles(self.free_rectangles)

                # 记录已使用的矩形
                self.used_rectangles.append(rect)
                results.append((rect_id, rect))

        return results

    def find_position(self, width, height, min_rectangle):
        """
        寻找最佳放置位置

        Args:
            width: 矩形宽度
            height: 矩形高度
            min_rectangle: 最小矩形尺寸

        Returns:
            最佳放置信息 (矩形, 所在空闲区域, 空闲区域索引) 或 None
        """
        new_free_rectangles = []
        best_score = float("inf")  # 最佳分数（越小越好）
        best_rect = None
        in_free_rect = None
        in_free_rect_idx = None

        # 遍历所有空闲区域
        for free_rect in self.free_rectangles:
            # 跳过过小的空闲区域
            if (
                free_rect.width < min_rectangle[1]
                or free_rect.height < min_rectangle[2]
            ):
                continue
            # 跳过无法容纳当前矩形的区域
            elif free_rect.width < width or free_rect.height < height:
                new_free_rectangles.append(free_rect)
                continue

            # 计算当前空闲区域的分数
            score = self.calculate_score(free_rect, MINAREA)

            # 更新最佳位置
            if score < best_score:
                best_score = score
                best_rect = Rectangle(free_rect.x, free_rect.y, width, height)
                in_free_rect = free_rect
                in_free_rect_idx = len(new_free_rectangles)

            # 保留当前空闲区域
            if free_rect not in new_free_rectangles:
                new_free_rectangles.append(free_rect)

        # 更新空闲区域列表
        self.free_rectangles = new_free_rectangles

        if best_rect:
            return best_rect, in_free_rect, in_free_rect_idx

        return None

    def calculate_score(self, rect, strategy):
        """
        计算矩形区域的分数

        Args:
            rect: 矩形区域
            strategy: 评分策略

        Returns:
            score: 分数值
        """
        if strategy == MINAREA:
            return rect.width * rect.height  # 使用面积作为评分

        return 0

    def split_free_rectangle(self, free_rect, used_rect, free_rect_idx):
        """
        分割空闲区域

        Args:
            free_rect: 原始空闲区域
            used_rect: 已使用的区域
            free_rect_idx: 空闲区域索引
        """
        right = None
        bottom = None

        # 检查右侧是否还有剩余空间
        if used_rect.x + used_rect.width != free_rect.x + free_rect.width:
            width = free_rect.x + free_rect.width - (used_rect.x + used_rect.width)
            height = free_rect.height

            right = Rectangle(
                x=used_rect.x + used_rect.width,
                y=free_rect.y,
                width=width,
                height=height,
            )

        # 检查下方是否还有剩余空间
        if used_rect.y + used_rect.height != free_rect.y + free_rect.height:
            width = used_rect.width
            height = free_rect.y + free_rect.height - (used_rect.y + used_rect.height)

            bottom = Rectangle(
                x=used_rect.x,
                y=used_rect.y + used_rect.height,
                width=width,
                height=height,
            )

        # 处理分割后的区域
        if right and bottom:
            # 调整区域边界避免重叠
            if right.width * right.height < free_rect.width * bottom.height:
                right, bottom = Rectangle(
                    right.x,
                    right.y,
                    right.width,
                    right.height - (bottom.height),
                ), Rectangle(bottom.x, bottom.y, free_rect.width, bottom.height)

            # 更新空闲区域列表
            self.free_rectangles[free_rect_idx] = right
            self.free_rectangles.append(bottom)
        elif right:
            self.free_rectangles[free_rect_idx] = right
        elif bottom:
            self.free_rectangles[free_rect_idx] = bottom

    def merge_free_rectangles(self, rectangles):
        """
        合并相邻的空闲矩形

        Args:
            rectangles: 待合并的矩形列表

        Returns:
            合并后的矩形列表
        """
        changed = True

        # 循环合并直到没有变化
        while changed and rectangles:
            changed = False
            rectangles.sort(key=lambda r: (r.y, r.x))  # 按位置排序

            # 使用临时列表记录要删除的索引
            to_remove = []

            i = 0
            while i < len(rectangles):
                if i in to_remove:
                    i += 1
                    continue

                merged = False
                j = i + 1

                # 尝试与后续矩形合并
                while j < len(rectangles):
                    if j in to_remove:
                        j += 1
                        continue

                    # 尝试合并两个矩形
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
        """
        尝试合并两个矩形

        Args:
            rect1: 第一个矩形
            rect2: 第二个矩形

        Returns:
            合并后的矩形或None（如果无法合并）
        """
        # 水平合并：Y坐标和高度相同，且rect1右侧紧邻rect2左侧
        if (
            rect1.y == rect2.y
            and rect1.height == rect2.height
            and rect1.x + rect1.width == rect2.x
        ):
            return Rectangle(rect1.x, rect1.y, rect1.width + rect2.width, rect1.height)

        # 垂直合并：X坐标和宽度相同，且rect1下方紧邻rect2上方
        if (
            rect1.x == rect2.x
            and rect1.width == rect2.width
            and rect1.y + rect1.height == rect2.y
        ):
            return Rectangle(rect1.x, rect1.y, rect1.width, rect1.height + rect2.height)

        return None


class CreateAtlas:
    """图集创建器，负责管理整个图集创建流程"""

    def __init__(self, images, atlas_name):
        """
        初始化图集创建器

        Args:
            images: 图片数据列表
            atlas_name: 图集名称
        """
        self.images = images
        self.atlas_name = atlas_name
        self.is_several_atlas = False  # 是否需要多个图集
        self.results = []  # 打包结果

    def create_atlas(self, rectangles, idx=1):
        """
        创建图集

        Args:
            rectangles: 矩形数据列表
            idx: 图集索引（用于多图集情况）
        """
        # 计算最优图集尺寸
        atlas_size, remaining_rect = self.calculate_optimal_size(rectangles, idx)

        # 使用MaxRects算法进行排列
        self.maxrects_packing(rectangles, atlas_size, idx)

        # 如果还有剩余矩形，创建下一个图集
        if self.is_several_atlas:
            self.is_several_atlas = False
            self.create_atlas(remaining_rect, idx + 1)

    def maxrects_packing(self, rectangles, atlas_size, idx):
        """
        使用MaxRects算法进行排列

        Args:
            rectangles: 矩形数据列表
            atlas_size: 图集尺寸 (width, height)
            idx: 图集索引
        """
        # 创建打包器实例
        packer = TexturePacker(atlas_size[0], atlas_size[1])

        # 执行排列算法
        results = packer.fit(rectangles)

        # 转换结果为实际位置信息
        for rect_id, rect in results:
            self.images[rect_id]["pos"] = v2(rect.x, rect.y)

        # 记录打包结果
        self.results.append(
            {
                "name": self.atlas_name + f"-{idx}",
                "rectangles_id": sorted([rect[0] for rect in results]),
                "atlas_size": atlas_size,
            }
        )

    def calculate_optimal_size(self, rectangles, idx):
        """
        计算最优的图集尺寸

        Args:
            rectangles: 矩形数据列表
            idx: 图集索引

        Returns:
            best_size: 最佳尺寸 (width, height)
            remaining_rect: 剩余未排列的矩形
        """
        remaining_rect = None

        # 尝试的标准尺寸序列
        sizes = [512, 1024, 2048, 4096]

        best_size = (sizes[0], sizes[0])

        # 遍历尺寸寻找最佳匹配
        for i, size in enumerate(sizes):
            # 模拟打包并计算利用率
            efficiency, remaining_rect = self.simulate_packing_efficiency(
                rectangles, size, size
            )

            if 0 < efficiency < trigger_several_efficiency:
                print(f"⚠️ {self.atlas_name}, {size}x{size}利用率较低，启用多图集打包")

                best_size = (sizes[i - 1], sizes[i - 1])
                self.is_several_atlas = True

                # 重新计算较小尺寸的利用率
                efficiency, remaining_rect = self.simulate_packing_efficiency(
                    rectangles, sizes[i - 1], sizes[i - 1]
                )
                break
            # 利用率可接受，使用当前尺寸
            elif efficiency > trigger_several_efficiency:
                best_size = (size, size)
                break
            elif efficiency == 0 and size == sizes[-1]:
                print(
                    f"⚠️ {self.atlas_name}, {size}x{size}尺寸无法容纳所有图片，启用多图集打包"
                )

                best_size = (size, size)
                self.is_several_atlas = True

        print(f"🏁 计算{self.atlas_name}-{idx}尺寸: {best_size[0]}x{best_size[1]}")

        return best_size, remaining_rect

    def simulate_packing_efficiency(self, rectangles, width, height):
        """
        模拟排列并计算空间利用率

        Args:
            rectangles: 矩形数据列表
            width: 模拟宽度
            height: 模拟高度

        Returns:
            efficiency: 空间利用率 (0-1)
            remaining_rect: 无法排列的矩形列表
        """
        # 创建临时打包器进行模拟
        packer = TexturePacker(width, height)
        results = packer.fit(rectangles)

        # 如果有矩形无法排列，返回剩余矩形
        if len(results) < len(rectangles):
            remaining_rect = [
                rect
                for rect in rectangles
                if rect[0] not in set([r[0] for r in results])
            ]
            return 0, remaining_rect

        # 计算空间利用率
        used_area = sum(img["width"] * img["height"] for img in self.images)
        total_area = width * height

        return used_area / total_area, []

    def save_to_dds(self, output_file, bc):
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
                str(output_path),
                str(output_file),
            ],
            capture_output=True,
            text=True,
        )

        # 删除临时PNG文件
        Path(output_file).unlink()

    def write_texture_atlas(self):
        """写入纹理图集文件"""
        for result in self.results:
            self.write_atlas(result["name"], result)

        self.write_lua_data()

    def write_atlas(self, filename, result):
        """
        创建并保存图集图片

        Args:
            filename: 输出文件名
            result: 打包结果数据
        """
        # 创建空白图集
        with Image.new(
            "RGBA", (result["atlas_size"][0], result["atlas_size"][1]), (0, 0, 0, 0)
        ) as atlas:
            output_file = output_path / f"{filename}.png"

            # 将所有图片粘贴到图集上
            for img_id in result["rectangles_id"]:
                img_info = self.images[img_id]
                img_pos = img_info["pos"]

                if img_pos:
                    position = (img_pos.x, img_pos.y)
                    atlas.paste(img_info["image"], position)

            # 在左上角添加白色像素（可能用于特殊用途，如血条）
            draw = ImageDraw.Draw(atlas)
            draw.rectangle([0, 0, 3, 3], "white", None, 0)

            # 保存PNG文件
            atlas.save(output_file)

            # 转换为DDS格式
            if output_format == "bc7":
                self.save_to_dds(output_file, 7)
            elif output_format == "bc3":
                self.save_to_dds(output_file, 3)
            elif output_format == "png":
                print(f"✅ 保存为png: {output_file.name}...")

    def write_lua_data(self):
        """生成Lua格式的图集数据文件"""
        filepath = output_path / f"{self.atlas_name}.lua"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("return {\n")

            # 遍历所有打包结果
            for result in self.results:
                for idx, img_id in enumerate(result["rectangles_id"]):
                    img = self.images[img_id]
                    pos = img["pos"]
                    trim = img["trim"]

                    # 写入图片数据
                    if is_simple_key(img["name"]):
                        f.write(f"\t{img["name"]} = {{\n")
                    else:
                        f.write(f'\t["{img["name"]}"] = {{\n')

                    if output_format == "png":
                        f.write(f'\t\ta_name = "{result["name"]}.png",\n')
                    else:
                        f.write(f'\t\ta_name = "{result["name"]}.dds",\n')

                    # 原始尺寸
                    f.write(f"\t\tsize = {{\n")
                    f.write(f"\t\t\t{img["origin_width"]},\n")
                    f.write(f"\t\t\t{img["origin_height"]}\n")
                    f.write(f"\t\t}},\n")

                    # 裁剪信息
                    f.write(f"\t\ttrim = {{\n")
                    f.write(f"\t\t\t{trim.left},\n")
                    f.write(f"\t\t\t{trim.top},\n")
                    f.write(f"\t\t\t{trim.right},\n")
                    f.write(f"\t\t\t{trim.bottom}\n")
                    f.write(f"\t\t}},\n")

                    # 图集尺寸
                    f.write(f"\t\ta_size = {{\n")
                    f.write(f"\t\t\t{result["atlas_size"][0]},\n")
                    f.write(f"\t\t\t{result["atlas_size"][1]}\n")
                    f.write(f"\t\t}},\n")

                    # 在图集中的位置和尺寸
                    f.write(f"\t\tf_quad = {{\n")
                    f.write(f"\t\t\t{pos.x},\n")
                    f.write(f"\t\t\t{pos.y},\n")
                    f.write(f"\t\t\t{img["width"]},\n")
                    f.write(f"\t\t\t{img["height"]}\n")
                    f.write(f"\t\t}},\n")

                    # 相同图片别名
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

                    # 结束当前图片数据
                    if idx == len(result["rectangles_id"]) - 1:
                        f.write(f"\t}}\n")
                    else:
                        f.write(f"\t}},\n")

            f.write("}")


def similarity_percentage(rc1, rc2):
    """
    计算两行或两列像素的相似度百分比

    Returns:
        avg_similarity: 差异值，值越大差异越大
    """
    if not (rc1 and rc2):
        return -1

    max_possible_diff = 4 * 255  # 最大可能差异
    diff = 0
    total_similarity = 0
    l = 0

    for pixel1, pixel2 in zip(rc1, rc2):
        if sum(pixel1) + sum(pixel2) > 0:
            for c1, c2 in zip(pixel1, pixel2):
                a = abs(c1 - c2)
                diff += a

            l += 1

    total_similarity += (diff / max_possible_diff)

    avg_similarity = total_similarity / l

    return round(avg_similarity, 2)


def fix_alignment_offset(img_a, img_b, direction, added, added_direction, trim_data):
    """
    修正两个图像之间偏移
    """
    left, top, right, bottom = trim_data

    best_offset = 0

    if direction == "x":
        row_a = []

        if added_direction == "top":
            for x in range(img_a.width):
                row_a.append(img_a.getpixel((x, 0)))

            for y in range(added):
                row_b = []

                for x in range(img_b.width):
                    row_b.append(img_b.getpixel((x, y)))

                if similarity_percentage(row_a, row_b) < 0.1:
                    best_offset += 1

        elif added_direction == "bottom":
            for x in range(img_a.width):
                row_a.append(img_a.getpixel((x, img_a.height - 1)))

            for y in range(img_b.height - 1, img_b.height - added, -1):
                row_b = []

                for x in range(img_b.width):
                    row_b.append(img_b.getpixel((x, y)))

                if similarity_percentage(row_a, row_b) < 0.1:
                    best_offset += 1

    elif direction == "y":
        column_a = []

        if added_direction == "left":
            for y in range(img_a.height):
                column_a.append(img_a.getpixel((0, y)))

            for x in range(added):
                column_b = []

                for y in range(img_b.height):
                    column_b.append(img_b.getpixel((x, y)))

                if similarity_percentage(column_a, column_b) < 0.1:
                    best_offset += 1

        if added_direction == "right":
            for y in range(img_a.height):
                column_a.append(img_a.getpixel((img_a.width - 1, y)))

            for x in range(added):
                column_b = []

                for y in range(img_b.height - 1, img_b.height - added):
                    column_b.append(img_b.getpixel((x, y)))

                if similarity_percentage(column_a, column_b) < 0.1:
                    best_offset += 1

    if best_offset:
        if added_direction == "left":
            left += best_offset
            right -= best_offset
        if added_direction == "right":
            left -= best_offset
            right += best_offset
        if added_direction == "top":
            top += best_offset
            bottom -= best_offset
        if added_direction == "bottom":
            left -= best_offset
            right += best_offset

    return v4(int(left), int(top), int(right), int(bottom))

def process_img(img, last_img_data):
    """
    处理单张图片：裁剪透明区域并计算裁剪信息

    Args:
        img: PIL图片对象
        last_img_data: 上一张图片的数据（用于对齐优化）

    Returns:
        new_img: 裁剪后的图片
        trim_data: 调整后的裁剪信息
        origin_trim_data: 原始裁剪信息
    """
    origin_width = img.width
    origin_height = img.height

    left = top = right = bottom = 0

    # 获取Alpha通道
    alpha = img.getchannel("A")

    # 获取非透明区域的边界框
    bbox = alpha.getbbox()
    if bbox:
        left, top, right, bottom = bbox

    right = origin_width - right
    bottom = origin_height - bottom

    # 裁剪图片
    new_img = img.crop(bbox)

    trim_data = v4(int(left), int(top), int(right), int(bottom))

    if last_img_data:
        last_img = last_img_data["image"]
        last_trim = last_img_data["trim"]

        def fix_alignment(direction, added, added_direction, trim_data):
            return fix_alignment_offset(
                last_img, new_img, direction, added, added_direction, trim_data
            )

        left_difference = left - last_trim.left
        right_difference = right - last_trim.right
        top_difference = top - last_trim.top
        bottom_difference = bottom - last_trim.bottom

        offset_x = offset_y = added_left = added_right = added_top = added_bottom = 0

        while left_difference * right_difference < 0:
            if left_difference < 0 and right_difference > 0:
                left_difference += 1
                right_difference -= 1

                offset_x -= 1
            elif left_difference > 0 and right_difference < 0:
                left_difference -= 1
                right_difference += 1

                offset_x += 1

        if left_difference != 0:
            added_left -= left_difference

            left_difference = 0
        elif right_difference != 0:
            added_right -= right_difference

            right_difference = 0

        while top_difference * bottom_difference < 0:
            if top_difference < 0 and bottom_difference > 0:
                top_difference += 1
                bottom_difference -= 1

                offset_y -= 1
            elif top_difference > 0 and bottom_difference < 0:
                top_difference -= 1
                bottom_difference += 1

                offset_y += 1

        if top_difference != 0:
            added_top -= top_difference

            top_difference = 0

        if bottom_difference != 0:
            added_bottom -= bottom_difference

            bottom_difference = 0

        if 0 < abs(offset_x) <= alignment_offset_fix:
            if offset_x > 0:
                left += offset_x
                right -= offset_x
            elif offset_x < 0:
                left -= offset_x
                right += offset_x

        if 0 < abs(offset_y) <= alignment_offset_fix:
            if offset_y > 0:
                top += offset_y
                bottom -= offset_y
            elif offset_y < 0:
                top -= offset_y
                bottom += offset_y

        trim_data = v4(int(left), int(top), int(right), int(bottom))

        # if 0 < added_left <= alignment_offset_fix:
        #     trim_data = fix_alignment("y", added_left, "left", trim_data)
        # if 0 < added_right <= alignment_offset_fix:
        #     trim_data = fix_alignment("y", added_right, "right", trim_data)
        # if 0 < added_top <= alignment_offset_fix:
        #     trim_data = fix_alignment("x", added_top, "top", trim_data)
        # if 0 < added_bottom <= alignment_offset_fix:
        #     trim_data = fix_alignment("x", added_bottom, "bottom", trim_data)

    return new_img, trim_data


def get_input_subdir():
    """
    加载输入目录中的所有图片并进行处理

    Returns:
        input_subdir: 按子目录组织的图片数据字典
    """
    last_img_data = None
    input_subdir = {}

    # try:
    # 遍历输入目录下的所有子目录
    for dir in input_path.iterdir():
        hash_groups = {}  # 用于检测重复图片

        input_subdir[dir.name] = {"images": [], "rectangles": []}
        images = input_subdir[dir.name]["images"]

        # 遍历子目录中的所有图片文件
        for image_file in Path(dir).iterdir():
            image_file_name = image_file.stem

            with Image.open(image_file) as img:
                # 计算图片哈希值用于重复检测
                hash_key = hashlib.md5(img.tobytes()).hexdigest()

                # 跳过重复图片
                if hash_key in hash_groups:
                    hash_group = hash_groups[hash_key]
                    hash_group["similar"].append(image_file_name)

                    print(f"跳过重复图片 {image_file.name}")
                    continue

                # 处理图片：裁剪透明区域
                new_img, trim = process_img(img, last_img_data)

                # 构建图片数据字典
                img_data = {
                    "path": image_file,
                    "image": new_img,
                    "width": new_img.width,
                    "height": new_img.height,
                    "origin_width": img.width,
                    "origin_height": img.height,
                    "name": image_file_name,
                    "samed_img": [],  # 相同图片列表
                    "removed": False,
                    "trim": trim,  # 裁剪信息
                }

                images.append(img_data)

                # 更新哈希分组
                if hash_key not in hash_groups:
                    hash_groups[hash_key] = {
                        "main": img_data,
                        "similar": img_data["samed_img"],
                    }

                last_img_data = img_data

                print(
                    f"📖 加载图片   {image_file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                )

            # 准备矩形数据用于打包 (id, width, height)
            rectangles = [
                (i, img["width"] + padding, img["height"] + padding)
                for i, img in enumerate(images)
            ]

            # 按面积降序排列
            input_subdir[dir.name]["rectangles"] = sorted(
                rectangles, key=lambda r: r[1] * r[2], reverse=True
            )

    # except Exception as e:
    #     print(f"加载图片时出错: {e}")
    #     traceback.print_exc()
    #     return

    return input_subdir


def main():
    """主函数：执行图集生成流程"""
    # 加载并处理输入图片
    input_subdir = get_input_subdir()

    print("所有图片加载完毕\n")

    if input_subdir:
        # 为每个子目录创建图集
        for atlas_name, subdir in input_subdir.items():
            atlas_name_stem = atlas_name.split("-")[0]

            images = subdir["images"]
            rectangles = subdir["rectangles"]

            # 创建图集实例
            create_texture_atlas = CreateAtlas(images, atlas_name_stem)

            # 执行图集创建流程
            create_texture_atlas.create_atlas(rectangles)

            # 输出图集文件
            create_texture_atlas.write_texture_atlas()

            print(f"{atlas_name_stem}图集生成完毕\n")

            # 释放图片资源
            for img_info in images:
                img_info["image"].close()


if __name__ == "__main__":
    # try:
    main()
    # except Exception as e:
    #     print(f"错误: {e}")
    #     traceback.print_exc()

    # 等待用户确认退出
    input("程序执行完毕，按回车键退出...")
