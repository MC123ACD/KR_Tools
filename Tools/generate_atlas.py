import traceback, config, hashlib, time, concurrent.futures, os, sys
from PIL import Image, ImageDraw
from utils import is_simple_key, save_to_dds, Point, Size, Rectangle, Bounds, run_app
from functools import wraps
from bisect import bisect_left, bisect_right
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import log

log = log.setup_logging(config.log_level, config.log_file)

# 最小面积策略标识
MIN_AREA = "min_area"
MAX_AREA = "max_area"
SHOR_TSIDE = "short_side"

TYPE_RECT = "rect"
TYPE_FREE_RECT = "free_rect"


class AtlasGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图集生成工具")
        self.root.geometry("600x250")

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建界面组件"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

        # 参数设置框架
        settings_frame = ttk.LabelFrame(main_frame, text="生成参数", padding="10")
        settings_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        # 创建两列布局
        left_column = ttk.Frame(settings_frame)
        left_column.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 20))

        right_column = ttk.Frame(settings_frame)
        right_column.grid(row=0, column=1, sticky=(tk.W, tk.E))

        # 左边列参数
        # 输出格式
        ttk.Label(left_column, text="输出格式:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.format_var = tk.StringVar(value=setting["output_format"])
        format_combo = ttk.Combobox(
            left_column,
            textvariable=self.format_var,
            values=["png", "bc3", "bc7"],
            width=15,
            state="readonly",
        )
        format_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        # 边框大小
        ttk.Label(left_column, text="边框大小:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.border_var = tk.IntVar(value=setting["border"])
        border_spin = ttk.Spinbox(
            left_column, from_=0, to=50, textvariable=self.border_var, width=15
        )
        border_spin.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        # 右边列参数
        # 内边距
        ttk.Label(right_column, text="内边距:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )
        self.padding_var = tk.IntVar(value=setting["padding"])
        padding_spin = ttk.Spinbox(
            right_column, from_=0, to=20, textvariable=self.padding_var, width=15
        )
        padding_spin.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        # 最大尺寸
        ttk.Label(right_column, text="最大尺寸:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.max_size_var = tk.IntVar(value=setting["max_size"])
        max_size_spin = ttk.Spinbox(
            right_column,
            from_=64,
            to=8192,
            increment=128,
            textvariable=self.max_size_var,
            width=15,
        )
        max_size_spin.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))

        # 复选框参数
        check_frame = ttk.Frame(settings_frame)
        check_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0)
        )

        self.add_white_var = tk.BooleanVar(value=setting["add_white_rect"])
        ttk.Checkbutton(
            check_frame, text="添加白色矩形", variable=self.add_white_var
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 20))

        self.delete_temp_var = tk.BooleanVar(value=setting["delete_temporary_png"])
        ttk.Checkbutton(
            check_frame, text="删除临时PNG文件", variable=self.delete_temp_var
        ).grid(row=0, column=1, sticky=tk.W)

        # 控制按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=(10, 5))

        self.start_button = ttk.Button(
            button_frame, text="开始生成", command=self.start_generation, width=30
        )
        self.start_button.grid(row=0, column=0, padx=(0, 10))

    def get_all_var(self):
        return {
            "format_var": self.format_var.get(),
            "border_var": self.border_var.get(),
            "padding_var": self.padding_var.get(),
            "max_size_var": self.max_size_var.get(),
            "add_white_var": self.add_white_var.get(),
            "delete_temp_var": self.delete_temp_var.get()
        }

    def start_generation(self):
        """开始生成图集"""
        global setting_var
        setting_var = self.get_all_var()

        try:
            # 加载并处理输入图片
            input_subdir = get_input_subdir()

            log.info("所有图像加载完毕\n")

            if not input_subdir:
                messagebox.showerror("错误", "未找到任何图像")
                return

            total_dirs = len(input_subdir)
            dir_count = 0

            # 为每个子目录创建图集
            for atlas_name, subdir in input_subdir.items():
                dir_count += 1
                atlas_stem_name = atlas_name.split("-")[0]

                images = subdir["images"]
                rectangles = subdir["rectangles"]

                # 执行图集创建流程
                results = create_atlas(atlas_stem_name, rectangles, images)

                # 输出图集文件
                for result in results:
                    result["atlas_size"] = write_atlas(images, result)

                # 生成Lua数据文件
                write_lua_data(images, results, atlas_stem_name)

                log.info(f"{atlas_stem_name}图集生成完毕\n")

                # 释放图片资源
                for img_info in images:
                    img_info["image"].close()

            messagebox.showinfo("完成", "所有图集已成功生成！")

        except Exception as e:
            messagebox.showerror("错误", f"生成图集时出错: {str(e)}")
            log.error(traceback.format_exc())


def process_img(img):
    """
    处理单张图片：裁剪透明区域并计算裁剪信息

    Args:
        img: PIL图片对象

    Returns:
        tuple: (裁剪后的图片, 裁剪信息元组)
    """
    origin_width = img.width
    origin_height = img.height

    left = top = right = bottom = 0

    bbox = img.getbbox() or (0, 0, 0, 0)

    left, top, right, bottom = bbox

    # 计算裁剪信息（相对于原始图片）
    right = origin_width - right
    bottom = origin_height - bottom

    # 裁剪图片
    new_img = img.crop(bbox)

    trim_data = Bounds(left, top, right, bottom)

    return new_img, trim_data


def calculate_image_hash(img):
    """
    计算图片哈希值，支持多种策略
    """
    # 策略1：使用图片数据哈希（准确但较慢）
    return hashlib.md5(img.tobytes()).hexdigest()


def process_single_image(image_file, hash_groups):
    """
    处理单张图片
    """
    image_file_name = image_file.stem

    # 5. 优化：先检查文件大小再计算哈希（快速跳过）
    file_size = image_file.stat().st_size
    if file_size == 0:
        log.warning(f"跳过空文件: {image_file.name}")
        return None

    with Image.open(image_file) as img:
        # 如果需要更快的速度，可以使用文件内容的哈希而不是图片数据的哈希
        hash_key = calculate_image_hash(img)

        # 跳过重复图片
        if hash_key in hash_groups:
            hash_group = hash_groups[hash_key]
            hash_group["similar"].append(image_file_name)
            log.info(f"跳过重复图片 {image_file.name}")
            return None

        # 处理图片：裁剪透明区域
        new_img, trim = process_img(img)

        # 构建图片数据字典
        img_data = {
            "name": image_file_name,
            "image": new_img,
            "origin_width": img.width,
            "origin_height": img.height,
            "samed_img": [],  # 相同图片列表
            "trim": trim,  # 裁剪信息
            "file_size": file_size,
            "aspect_ratio": img.width / img.height if img.height > 0 else 0,
        }

        # 更新哈希分组
        hash_groups[hash_key] = {
            "main": img_data,
            "similar": img_data["samed_img"],
        }

        log.debug(
            f"加载图片 {image_file.name} "
            f"({img.width}x{img.height} → {new_img.width}x{new_img.height}) "
            f"大小: {file_size:,} bytes"
        )

        return img_data


def process_directory(directory_path, padding):
    """
    处理单个目录的图片
    """
    hash_groups = {}  # 用于检测重复图片
    images = []

    # 预收集所有图片文件路径
    image_files = list(directory_path.glob("*.*"))
    image_files = [
        f for f in image_files if f.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]

    # 2. 批量处理图片（减少IO操作）
    for image_file in image_files:
        log.info(f"📂 处理图片: {image_file.name}...")
        try:
            image_data = process_single_image(image_file, hash_groups)
            if image_data:
                images.append(image_data)
        except Exception as e:
            log.error(f"处理图片 {image_file.name} 失败: {e}")
            continue

    if not images:
        return None

    # 3. 准备矩形数据（使用生成器表达式）
    rectangles = [
        (
            i,
            img["name"],
            Size(img["image"].width + padding, img["image"].height + padding),
        )
        for i, img in enumerate(images)
    ]

    # 4. 使用更高效的排序
    rectangles.sort(key=lambda r: r[2].w, reverse=True)

    return {"images": images, "rectangles": rectangles}


def get_input_subdir():
    """
    加载输入目录中的所有图片并进行处理

    Returns:
        dict: 按子目录组织的图片数据字典
    """
    input_subdir = {}
    padding = setting_var["padding_var"]

    # 1. 并行处理子目录
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(4, (os.cpu_count() or 2))
    ) as executor:
        # 提交所有子目录处理任务
        future_to_dir = {
            executor.submit(process_directory, item, padding): item.name
            for item in config.input_path.iterdir()
            if item.is_dir()
        }

        # 收集结果
        for future in concurrent.futures.as_completed(future_to_dir):
            dir_name = future_to_dir[future]
            result = future.result()
            if result:
                input_subdir[dir_name] = result

    return input_subdir


def calculate_score(rect, strategy):
    """
    计算矩形区域的分数，用于选择最佳放置位置

    Args:
        rect: 待评估的矩形区域
        strategy: 评分策略，目前仅支持最小面积策略

    Returns:
        float: 分数值，分数越小表示越优先选择
    """
    if strategy == MIN_AREA:
        return rect.area()  # 使用面积作为评分
    elif strategy == SHOR_TSIDE:
        return min(rect.w, rect.h)  # 使用短边长度作为评分
    elif strategy == MAX_AREA:
        return -rect.area()  # 使用面积作为评分

    return 0


def calculate_optimal_size(rectangles):
    """
    计算最优的图集尺寸

    通过尝试不同尺寸，找到空间利用率最高的图集尺寸

    Args:
        rectangles: 矩形数据列表

    Returns:
        tuple: 最佳尺寸 Vector(width, height)
    """
    total_area = sum(rect[2].area() for rect in rectangles)
    sqrt_area = int(total_area**0.5 * 1.1)

    size = 1 << sqrt_area.bit_length()

    if size > setting_var["max_size_var"]:
        size = setting_var["max_size_var"]

    size = Size(size, size)

    return size


def find_position(free_rectangles, rect):
    """
    在空闲区域中寻找最佳放置位置

    Args:
        free_rectangles: 当前空闲区域列表
        width: 待放置矩形的宽度
        height: 待放置矩形的高度

    Returns:
        tuple: (更新后的空闲区域列表, (最佳矩形, 所在空闲区域, 空闲区域索引)) 或 None
    """
    best_score = float("inf")  # 最佳分数（越小越好）
    best_rect = in_free_rect = in_free_rect_idx = None

    # 遍历所有空闲区域
    for i, free_rect in enumerate(free_rectangles):
        # 跳过无法容纳当前矩形的区域
        if free_rect.w < rect.w or free_rect.h < rect.h:
            continue

        # 计算当前空闲区域的分数
        score = calculate_score(free_rect, MIN_AREA)

        # 更新最佳位置
        if score < best_score:
            best_score = score
            best_rect = Rectangle(free_rect.x, free_rect.y, rect.w, rect.h)
            in_free_rect = free_rect
            in_free_rect_idx = i

    if best_rect:
        return best_rect, in_free_rect, in_free_rect_idx

    return None


def split_free_rectangle(free_rectangles, free_rect, used_rect, free_rect_idx):
    """
    将空闲区域分割为剩余空间

    当在一个空闲区域中放置矩形后，将剩余空间分割为右侧和下方的两个新空闲区域

    Args:
        free_rectangles: 当前空闲区域列表
        free_rect: 被使用的空闲区域
        used_rect: 已放置的矩形区域
        free_rect_idx: 被使用的空闲区域在列表中的索引
    """
    new_rects = []

    # 检查右侧是否还有剩余空间
    if used_rect.x + used_rect.w != free_rect.x + free_rect.w:
        new_rects.append(
            Rectangle(
                used_rect.x + used_rect.w,
                free_rect.y,
                free_rect.x + free_rect.w - (used_rect.x + used_rect.w),
                free_rect.h,
            )
        )

    # 检查下方是否还有剩余空间
    if used_rect.y + used_rect.h != free_rect.y + free_rect.h:
        new_rects.append(
            Rectangle(
                used_rect.x,
                used_rect.y + used_rect.h,
                used_rect.w,
                free_rect.y + free_rect.h - (used_rect.y + used_rect.h),
            )
        )

    if not new_rects:
        # 如果空间完全被使用，标记为空矩形
        free_rectangles[free_rect_idx] = Rectangle(0, 0, 0, 0)
        return

    free_rectangles[free_rect_idx] = new_rects[0]
    free_rectangles.extend(new_rects[1:])


def try_merge_rectangles(rect1, rect2):
    """
    尝试合并两个相邻的矩形

    支持水平合并（左右相邻）和垂直合并（上下相邻）

    Args:
        rect1: 第一个矩形
        rect2: 第二个矩形

    Returns:
        Rectangle: 合并后的矩形，如果无法合并则返回None
    """
    # 水平合并：Y坐标和高度相同，且rect1右侧紧邻rect2左侧
    if rect1.y == rect2.y and rect1.h == rect2.h:
        if rect1.x + rect1.w == rect2.x:
            return Rectangle(rect1.x, rect1.y, rect1.w + rect2.w, rect1.h)

        if rect2.x + rect2.w == rect1.x:
            return Rectangle(rect2.x, rect2.y, rect1.w + rect2.w, rect1.h)

    # 垂直合并：X坐标和宽度相同，且rect1下方紧邻rect2上方
    if rect1.x == rect2.x and rect1.w == rect2.w:
        if rect1.y + rect1.h == rect2.y:
            return Rectangle(rect1.x, rect1.y, rect1.w, rect1.h + rect2.h)

        if rect2.y + rect2.h == rect1.y:
            return Rectangle(rect2.x, rect2.y, rect1.w, rect1.h + rect2.h)

    return None


def merge_single_free_rect(merged_idx, free_rect, sorted_by_x, x_coords):
    merged_rect = None

    # 使用二分查找找到可能可以合并的矩形
    start_idx = bisect_left(x_coords, free_rect.x - free_rect.w)  # 调整搜索范围

    for i in range(start_idx, len(sorted_by_x)):
        if i in merged_idx:
            continue
        other_free_rect = sorted_by_x[i]

        if other_free_rect.x > free_rect.x + free_rect.w:
            break

        merged_rect = try_merge_rectangles(free_rect, other_free_rect)
        if not merged_rect:
            continue

        merged_idx.add(i)

        other_merged_rect = merge_single_free_rect(
            merged_idx, merged_rect, sorted_by_x, x_coords
        )
        if other_merged_rect:
            merged_rect = other_merged_rect

        break

    return merged_rect


def merge_free_rectangles(free_rectangles):
    """
    合并相邻的空闲矩形
    """
    if not free_rectangles:
        return []

    # 使用类似R-tree的空间索引优化
    # 按x坐标排序并建立索引
    sorted_by_x = sorted(free_rectangles, key=lambda r: r.x)
    x_coords = [r.x for r in sorted_by_x]

    merged_idx = set()
    merged = []

    for free_rect_idx in range(len(sorted_by_x)):
        if free_rect_idx in merged_idx:
            continue

        free_rect = sorted_by_x[free_rect_idx]

        merged_rect = merge_single_free_rect(
            merged_idx, free_rect, sorted_by_x, x_coords
        )

        if merged_rect:
            merged_idx.add(free_rect_idx)
            merged.append(merged_rect)
        else:
            merged.append(free_rect)

    return merged


def guillotine_packing(rectangles, atlas_size):
    """
    使用Guillotine算法在指定尺寸的画布上排列矩形

    Args:
        rectangles: 待排列的矩形列表，格式为[(id, width, height), ...]
        width: 画布宽度
        height: 画布高度

    Returns:
        list: 排列结果列表，格式为[(rect_id, Rectangle), ...]
    """
    border = setting_var["border_var"]
    result_rectangles = []
    # 初始化空闲区域为整个画布（考虑边框）
    free_rectangles = [
        Rectangle(border, border, atlas_size.w - border, atlas_size.h - border)
    ]

    # 遍历所有矩形进行排列
    for rect_id, rect_name, rect in rectangles:
        # 寻找最佳放置位置
        rect_data = find_position(free_rectangles, rect)

        if rect_data:
            used_rect, in_free_rect, free_rect_idx = rect_data

            split_free_rectangle(
                free_rectangles, in_free_rect, used_rect, free_rect_idx
            )
            free_rectangles = merge_free_rectangles(free_rectangles)

            result_rectangles.append((rect_id, rect_name, used_rect))

    return result_rectangles


def create_atlas(baisic_atlas_name, rectangles, images):
    """
    创建图集

    可能生成多个图集（如果图片无法全部放入一个图集）

    Args:
        baisic_atlas_name: 图集基础名称
        rectangles: 矩形数据列表
        images: 图片数据字典

    Returns:
        list: 所有生成图集的结果信息列表
    """
    idx = 1
    final_results = []

    while True:
        # 生成图集名称（多图集时添加序号）
        atlas_name = baisic_atlas_name + f"-{idx}"

        # 计算最优尺寸
        atlas_size = calculate_optimal_size(rectangles)

        log.info(f"🏁 计算{atlas_name}尺寸: {atlas_size}")

        # 使用Guillotine算法进行排列
        result_rectangles = guillotine_packing(rectangles, atlas_size)

        result_rectangles.sort(key=lambda r: r[1])

        # 记录打包结果
        final_results.append(
            {
                "name": atlas_name,
                "rectangles": result_rectangles,
                "atlas_size": atlas_size,
            }
        )

        # 更新图片位置信息
        for rect_id, _, rect in result_rectangles:
            images[rect_id]["pos"] = Point(rect.x, rect.y)

        # 计算剩余未打包的矩形
        packed_ids = set(rect[0] for rect in result_rectangles)
        remaining_rects = [rect for rect in rectangles if rect[0] not in packed_ids]

        if not remaining_rects:
            break

        log.info(f"🔄 还有 {len(remaining_rects)} 个矩形未打包，准备下一轮打包")
        rectangles = remaining_rects
        idx += 1

    return final_results


def write_atlas(images, result):
    """
    创建并保存图集图片

    Args:
        images: 图片数据字典
        result: 打包结果数据
    """
    # 创建空白图集
    with Image.new("RGBA", tuple(result["atlas_size"]), (0, 0, 0, 0)) as atlas:
        output_file = config.output_path / f"{result['name']}.png"

        # 将所有图片粘贴到图集上
        for rect in result["rectangles"]:
            img_id = rect[0]
            img_info = images[img_id]
            img_pos = img_info["pos"]

            if img_pos:
                atlas.paste(img_info["image"], tuple(img_pos))

        # 在左上角添加白色像素（用于特殊用途，如血条占位）
        if setting_var["add_white_var"]:
            draw = ImageDraw.Draw(atlas)
            draw.rectangle(
                list(Rectangle(0, 0, 3, 3)),
                (255, 255, 255, 255),
                None,
            )

        # 裁剪图集到实际内容大小
        bbox = atlas.getbbox()
        if bbox:
            border = setting_var["border_var"]
            left, top, right, bottom = bbox

            right_alignment = 4 - (right % 4)
            bottom_alignment = 4 - (bottom % 4)
            right += right_alignment
            bottom += bottom_alignment

            right_border = max(0, border - right_alignment)
            bottom_border = max(0, border - bottom_alignment)
            right_border += 4 - (right_border % 4)
            bottom_border += 4 - (bottom_border % 4)

            atlas = atlas.crop(
                (left, top, right + right_border, bottom + bottom_border)
            )

        # 保存PNG文件
        atlas.save(output_file)

        output_format = setting_var["format_var"]

        # 转换为DDS格式（如果需要）
        if output_format == "bc7" or output_format == "bc3":
            save_to_dds(
                output_file,
                config.output_path,
                output_format,
                setting_var["delete_temp_var"],
            )
        elif output_format == "png":
            log.info(f"✅ 保存为png: {output_file.name}...")

        return Size(atlas.width, atlas.height)


def write_lua_data(images, results, atlas_name):
    """
    生成Lua格式的图集数据文件

    包含每张图片在图集中的位置、尺寸、裁剪等信息

    Args:
        images: 图片数据字典
        results: 打包结果列表
        atlas_name: 图集名称
    """
    content = ["return {"]

    def a(str):
        content.append(str)

    # 遍历所有打包结果
    for i, result in enumerate(results):
        for j, rect in enumerate(result["rectangles"]):
            img_id = rect[0]
            img = images[img_id]
            pos = img["pos"]
            trim = img["trim"]

            # 写入图片数据
            if is_simple_key(img["name"]):
                a(f"\t{img['name']} = {{")
            else:
                a(f'\t["{img["name"]}"] = {{')

            # 图集文件名
            if setting_var["format_var"] == "png":
                a(f'\t\ta_name = "{result["name"]}.png",')
            else:
                a(f'\t\ta_name = "{result["name"]}.dds",')

            # 原始尺寸
            a(f"\t\tsize = {{")
            a(f"\t\t\t{img['origin_width']},")
            a(f"\t\t\t{img['origin_height']}")
            a("\t\t},")

            tleft, ttop, tright, tbottom = trim

            # 裁剪信息
            a("\t\ttrim = {")
            a(f"\t\t\t{tleft},")
            a(f"\t\t\t{ttop},")
            a(f"\t\t\t{tright},")
            a(f"\t\t\t{tbottom}")
            a("\t\t},")

            # 图集尺寸
            a("\t\ta_size = {")
            a(f"\t\t\t{result['atlas_size'].w},")
            a(f"\t\t\t{result['atlas_size'].h}")
            a("\t\t},")

            # 在图集中的位置和尺寸
            a("\t\tf_quad = {")
            a(f"\t\t\t{pos.x},")
            a(f"\t\t\t{pos.y},")
            a(f"\t\t\t{img['image'].width},")
            a(f"\t\t\t{img['image'].height}")
            a("\t\t},")

            # 相同图片别名
            if len(img["samed_img"]) > 0:
                a("\t\talias = {")
                for ii, name in enumerate(img["samed_img"]):
                    if ii < len(img["samed_img"]) - 1:
                        a(f'\t\t\t"{name}",')
                    else:
                        a(f'\t\t\t"{name}"')
                a("\t\t}")
            else:
                a("\t\talias = {}")

            # 结束当前图片数据
            if i < len(results) - 1 or j < len(result["rectangles"]) - 1:
                a("\t},")
            else:
                a("\t}")

    a("}")

    filepath = config.output_path / f"{atlas_name}.lua"

    lua_content = "\n".join(content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(lua_content)


# def add_performance_monitor_decorator():
#     all_time = {}

#     def timer_decorator(func):
#         """计时装饰器"""

#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             start = time.perf_counter()
#             result = func(*args, **kwargs)
#             end = time.perf_counter()

#             if not all_time.get(func.__name__):
#                 all_time[func.__name__] = []

#             all_time[func.__name__].append(end - start)

#             return result

#         return wrapper

#     global get_input_subdir
#     get_input_subdir = timer_decorator(get_input_subdir)
#     global find_position
#     find_position = timer_decorator(find_position)
#     global calculate_optimal_size
#     calculate_optimal_size = timer_decorator(calculate_optimal_size)
#     global merge_free_rectangles
#     merge_free_rectangles = timer_decorator(merge_free_rectangles)
#     global split_free_rectangle
#     split_free_rectangle = timer_decorator(split_free_rectangle)

#     return all_time


# def print_performance_info(all_time):
#     sum_time = 0
#     calculated_sum = []

#     for fn_name, time_list in all_time.items():
#         s = sum([t for t in time_list])

#         count = len(time_list)

#         calculated_sum.append((fn_name, s, count))
#         sum_time += s

#     calculated_sum.sort(key=lambda x: x[1], reverse=True)

#     log.info(f"\n=====总运行时长: {sum_time:.3f} 秒=====")

#     for fn_name, s, count in calculated_sum:
#         log.info(
#             f"{fn_name:<25}: {int(s * 1000)} ms, {count:>5} 次 ({s/sum_time*100:<6.2f}%)"
#         )


def main(root=None):
    global setting
    setting = config.setting["generate_atlas"]
    run_app(root, AtlasGeneratorApp)


if __name__ == "__main__":
    main()
