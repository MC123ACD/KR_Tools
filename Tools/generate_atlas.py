import traceback, config, hashlib, time, concurrent.futures, os
from PIL import Image, ImageDraw
from utils import is_simple_key, save_to_dds, Vector, Rectangle
from functools import wraps
from bisect import bisect_left

import log

log = log.setup_logging(config.log_level, config.log_file)

# 加载生成图集的配置
setting = config.setting["generate_atlas"]

# 最小面积策略标识
MINAREA = "min_area"
SHORTSIDE = "short_side"
MAXAREA = "max_area"

def calculate_score(rect, strategy):
    """
    计算矩形区域的分数，用于选择最佳放置位置

    Args:
        rect: 待评估的矩形区域
        strategy: 评分策略，目前仅支持最小面积策略

    Returns:
        float: 分数值，分数越小表示越优先选择
    """
    if strategy == MINAREA:
        return rect.w * rect.h  # 使用面积作为评分
    elif strategy == SHORTSIDE:
        return min(rect.w, rect.h)  # 使用短边长度作为评分
    elif strategy == MAXAREA:
        return -rect.w * rect.h  # 使用面积作为评分

    return 0


def find_position(free_rectangles, width, height):
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
        if free_rect.w < width or free_rect.h < height:
            continue

        # 计算当前空闲区域的分数
        score = calculate_score(free_rect, MINAREA)

        # 更新最佳位置
        if score < best_score:
            best_score = score
            best_rect = Rectangle(free_rect.x, free_rect.y, width, height, int)
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

    # 检查左侧是否还有剩余空间
    if used_rect.x != free_rect.x:
        new_rects.append(
            Rectangle(
                free_rect.x, free_rect.y, used_rect.x - free_rect.x, free_rect.h, int
            )
        )

    # 检查右侧是否还有剩余空间
    if used_rect.x + used_rect.w != free_rect.x + free_rect.w:
        new_rects.append(
            Rectangle(
                used_rect.x + used_rect.w,
                free_rect.y,
                free_rect.x + free_rect.w - (used_rect.x + used_rect.w),
                free_rect.h,
                int,
            )
        )

    # 检查上方是否还有剩余空间
    if used_rect.y != free_rect.y:
        new_rects.append(
            Rectangle(
                used_rect.x, free_rect.y, used_rect.w, used_rect.y - free_rect.y, int
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
                int,
            )
        )

    if not new_rects:
        # 如果空间完全被使用，标记为空矩形
        free_rectangles[free_rect_idx] = Rectangle(0, 0, 0, 0, int)
        return

    # 用第一个非空闲区域替换当前空闲区域
    free_rectangles[free_rect_idx] = new_rects[0]
    free_rectangles.extend(new_rects[1:])


def delete_invalid_rectangles(free_rectangles, min_rectangle):
    removed_idx = set()

    # 删除过小的空闲区域
    for i in range(len(free_rectangles)):
        free_rect = free_rectangles[i]

        if free_rect.w < min_rectangle[1] or free_rect.h < min_rectangle[2]:
            removed_idx.add(i)

    for idx in sorted(removed_idx, reverse=True):
        del free_rectangles[idx]


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
    if rect1.y == rect2.y and rect1.h == rect2.h and rect1.x + rect1.w == rect2.x:
        return Rectangle(rect1.x, rect1.y, rect1.w + rect2.w, rect1.h, int)

    # 垂直合并：X坐标和宽度相同，且rect1下方紧邻rect2上方
    if rect1.x == rect2.x and rect1.w == rect2.w and rect1.y + rect1.h == rect2.y:
        return Rectangle(rect1.x, rect1.y, rect1.w, rect1.h + rect2.h, int)

    return None


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

    merged = []

    for rect in sorted_by_x:
        # 使用二分查找找到可能重叠的矩形
        start_idx = bisect_left(x_coords, rect.x - rect.w)  # 调整搜索范围
        found_merge = False

        for i in range(start_idx, len(sorted_by_x)):
            if sorted_by_x[i].x > rect.x + rect.w:
                break

            if sorted_by_x[i] == rect:
                continue

            merged_rect = try_merge_rectangles(rect, sorted_by_x[i])
            if merged_rect:
                # 更新矩形和坐标列表
                rect = merged_rect
                # 移除被合并的矩形
                del sorted_by_x[i]
                del x_coords[i]
                found_merge = True
                break

        if not found_merge:
            merged.append(rect)

    return merged


def maxrects_packing(rectangles, width, height):
    """
    使用MaxRects算法在指定尺寸的画布上排列矩形

    Args:
        rectangles: 待排列的矩形列表，格式为[(id, width, height), ...]
        width: 画布宽度
        height: 画布高度

    Returns:
        list: 排列结果列表，格式为[(rect_id, Rectangle), ...]
    """
    border = setting["border"]
    results = []
    # 初始化空闲区域为整个画布（考虑边框）
    free_rectangles = [Rectangle(border, border, width - border, height - border)]

    # 获取最小的矩形（用于优化判断）
    min_rectangle = rectangles[-1]

    # 遍历所有矩形进行排列
    for rect_id, w, h in rectangles:
        # 寻找最佳放置位置
        rect_data = find_position(free_rectangles, w, h)

        if rect_data:
            rect, in_free_rect, free_rect_idx = rect_data

            split_free_rectangle(free_rectangles, in_free_rect, rect, free_rect_idx)
            delete_invalid_rectangles(free_rectangles, min_rectangle)
            free_rectangles = merge_free_rectangles(free_rectangles)

            for existing_id, existing_rect in results:
                if rect.other_pos(existing_rect) == ["in"]:
                    log.warning(f"⚠️  警告: 矩形 {rect_id} 与矩形 {existing_id} 重叠!")

            for free_rect in free_rectangles:
                if in_free_rect.other_pos(free_rect) == ["in"]:
                    log.warning(
                        f"⚠️  警告: 空闲区域 {in_free_rect} 与空闲区域 {free_rect} 重叠!"
                    )

            results.append((rect_id, rect))

    return results


def calculate_optimal_size(rectangles):
    """
    计算最优的图集尺寸

    通过尝试不同尺寸，找到空间利用率最高的图集尺寸

    Args:
        rectangles: 矩形数据列表

    Returns:
        tuple: 最佳尺寸 Vector(width, height)
    """
    total_area = sum(rect[1] * rect[2] for rect in rectangles)
    sqrt_area = int(total_area**0.5) + total_area // 10

    size = 1 << sqrt_area.bit_length()

    if size > setting["max_size"]:
        size = setting["max_size"]

    size = Vector(size, size, int)

    return size


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
    finish_results = []

    while True:
        # 生成图集名称（多图集时添加序号）
        atlas_name = baisic_atlas_name + f"-{idx}"

        # 计算最优尺寸
        atlas_size = calculate_optimal_size(rectangles)

        log.info(f"🏁 计算{atlas_name}尺寸: {atlas_size.x}x{atlas_size.y}")

        # 使用MaxRects算法进行排列
        results = maxrects_packing(rectangles, atlas_size.x, atlas_size.y)

        # 记录打包结果
        finish_results.append(
            {
                "name": atlas_name,
                "rectangles_id": sorted([rect[0] for rect in results]),
                "atlas_size": atlas_size,
            }
        )

        # 更新图片位置信息
        for rect_id, rect in results:
            images[rect_id]["pos"] = Vector(rect.x, rect.y, int)

        # 计算剩余未打包的矩形
        packed_ids = set(rect[0] for rect in results)
        remaining_rect = [rect for rect in rectangles if rect[0] not in packed_ids]

        if not remaining_rect:
            break

        log.info(f"🔄 还有 {len(remaining_rect)} 个矩形未打包，准备下一轮打包")
        rectangles = remaining_rect
        idx += 1

    return finish_results

def write_atlas(images, result):
    """
    创建并保存图集图片

    Args:
        images: 图片数据字典
        result: 打包结果数据
    """
    # 创建空白图集
    with Image.new(
        "RGBA", (result["atlas_size"].x, result["atlas_size"].y), (0, 0, 0, 0)
    ) as atlas:
        output_file = config.output_path / f"{result['name']}.png"

        # 将所有图片粘贴到图集上
        for img_id in result["rectangles_id"]:
            img_info = images[img_id]
            img_pos = img_info["pos"]

            if img_pos:
                position = (img_pos.x, img_pos.y)
                atlas.paste(img_info["image"], position)

        # 在左上角添加白色像素（用于特殊用途，如血条占位）
        if setting["add_white_rect"]:
            draw = ImageDraw.Draw(atlas)
            ww, wh = setting["white_rect_size"]
            draw.rectangle([0, 0, ww, wh], "white", None, 0)

        if not setting["generate_square"]:
            # 裁剪图集到实际内容大小
            bbox = atlas.getbbox()
            if bbox:
                left, top, right, bottom = bbox

                right += 4 - (right % 4)
                bottom += 4 - (bottom % 4)

                atlas = atlas.crop((left, top, right, bottom))

        # 保存PNG文件
        atlas.save(output_file)

        # 转换为DDS格式（如果需要）
        if setting["output_format"] == "bc7" or setting["output_format"] == "bc3":
            save_to_dds(
                output_file,
                config.output_path,
                setting["output_format"],
                setting["delete_temporary_png"],
            )
        elif setting["output_format"] == "png":
            log.info(f"✅ 保存为png: {output_file.name}...")

        return Vector(atlas.width, atlas.height, int)


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
        for j, img_id in enumerate(result["rectangles_id"]):
            img = images[img_id]
            pos = img["pos"]
            trim = img["trim"]

            # 写入图片数据
            if is_simple_key(img["name"]):
                a(f"\t{img['name']} = {{")
            else:
                a(f'\t["{img["name"]}"] = {{')

            # 图集文件名
            if setting["output_format"] == "png":
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
            a(f"\t\t\t{result['atlas_size'].x},")
            a(f"\t\t\t{result['atlas_size'].y}")
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
            if i < len(results) - 1 or j < len(result["rectangles_id"]) - 1:
                a("\t},")
            else:
                a("\t}")

    a("}")

    filepath = config.output_path / f"{atlas_name}.lua"

    lua_content = "\n".join(content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(lua_content)


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

    # 确保图片有Alpha通道
    if img.mode == "RGB":
        img = img.convert("RGBA")

    # 获取非透明区域的边界框
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()

    if not bbox:
        return img, (0, 0, 0, 0)

    left, top, right, bottom = bbox

    # 计算裁剪信息（相对于原始图片）
    right = origin_width - right
    bottom = origin_height - bottom

    # 裁剪图片
    new_img = img.crop(bbox)

    trim_data = (int(left), int(top), int(right), int(bottom))

    return new_img, trim_data


def get_input_subdir():
    """
    加载输入目录中的所有图片并进行处理

    Returns:
        dict: 按子目录组织的图片数据字典
    """
    input_subdir = {}
    padding = setting["padding"]

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
            try:
                result = future.result()
                if result:
                    input_subdir[dir_name] = result
            except Exception as exc:
                log.error(f"处理目录 {dir_name} 时出错: {exc}")

    return input_subdir


def process_directory(directory_path, padding):
    """
    处理单个目录的图片
    """
    hash_groups = {}  # 用于检测重复图片
    images = []

    # 预收集所有图片文件路径
    image_files = list(directory_path.glob("*.*"))
    image_files = [
        f
        for f in image_files
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
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
        (i, img["image"].width + padding, img["image"].height + padding)
        for i, img in enumerate(images)
    ]

    # 4. 使用更高效的排序
    rectangles.sort(key=lambda r: (r[1], r[1] * r[2]), reverse=True)

    return {"images": images, "rectangles": rectangles}


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


def calculate_image_hash(img):
    """
    计算图片哈希值，支持多种策略
    """
    # 策略1：使用图片数据哈希（准确但较慢）
    return hashlib.md5(img.tobytes()).hexdigest()

    # # 策略2：使用缩略图哈希（更快，适用于大多数重复检测）
    # thumbnail = img.copy()
    # thumbnail.thumbnail((64, 64))  # 缩放到64x64
    # return hashlib.md5(thumbnail.tobytes()).hexdigest()


def main():
    """
    主函数：执行图集生成流程

    流程：
    1. 加载并处理输入图片
    2. 为每个子目录创建图集
    3. 使用MaxRects算法排列图片
    4. 生成图集图片文件
    5. 生成Lua数据文件
    """
    # 加载并处理输入图片
    input_subdir = get_input_subdir()

    log.info("所有图片加载完毕\n")

    if not input_subdir:
        log.info("未找到任何图片")
        return

    # 为每个子目录创建图集
    for atlas_name, subdir in input_subdir.items():
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

    log.info("所有图集生成完毕")


def add_performance_monitor_decorator():
    all_time = {}

    def timer_decorator(func):
        """计时装饰器"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()

            if not all_time.get(func.__name__):
                all_time[func.__name__] = []

            all_time[func.__name__].append(end - start)

            return result

        return wrapper

    global get_input_subdir
    get_input_subdir = timer_decorator(get_input_subdir)
    global find_position
    find_position = timer_decorator(find_position)
    global calculate_optimal_size
    calculate_optimal_size = timer_decorator(calculate_optimal_size)
    global merge_free_rectangles
    merge_free_rectangles = timer_decorator(merge_free_rectangles)
    global split_free_rectangle
    split_free_rectangle = timer_decorator(split_free_rectangle)

    return all_time


def print_performance_info(all_time):
    sum_time = 0
    calculated_sum = []

    for fn_name, time in all_time.items():
        s = sum([t for t in time])

        count = len(time)

        calculated_sum.append((fn_name, s, count))
        sum_time += s

    calculated_sum.sort(key=lambda x: x[1], reverse=True)

    log.info(f"\n=====总运行时长: {sum_time:.3f} 秒=====")

    for fn_name, s, count in calculated_sum:
        log.info(f"{fn_name:<25}: {s:.3f} 秒, {count:>5} 次 ({s/sum_time*100:<6.2f}%)")


def performance_monitor(main):
    def new_main(*args, **kwargs):
        all_time = add_performance_monitor_decorator()
        result = main(*args, **kwargs)
        print_performance_info(all_time)

        return result

    return new_main


if setting["performance_monitor_enabled"]:
    main = performance_monitor(main)
