import traceback, config, hashlib
from PIL import Image, ImageDraw
from utils import is_simple_key, save_to_dds, Vector, Rectangle

setting = config.setting["generate_atlas"]

MINAREA = "min_area"  # 最小面积策略标识


def try_merge_rectangles(rect1, rect2):
    """
    尝试合并两个矩形

    Args:
        rect1: 第一个矩形
        rect2: 第二个矩形

    Returns:
        合并后的矩形或None（如果无法合并）
    """
    # 水平合并：Y坐标和高度相同，且rect1右侧紧邻rect2左侧
    if rect1.y == rect2.y and rect1.h == rect2.h and rect1.x + rect1.w == rect2.x:
        return Rectangle(rect1.x, rect1.y, rect1.w + rect2.w, rect1.h)

    # 垂直合并：X坐标和宽度相同，且rect1下方紧邻rect2上方
    if rect1.x == rect2.x and rect1.w == rect2.w and rect1.y + rect1.h == rect2.y:
        return Rectangle(rect1.x, rect1.y, rect1.w, rect1.h + rect2.h)

    return None


def calculate_score(rect, strategy):
    """
    计算矩形区域的分数

    Args:
        rect: 矩形区域
        strategy: 评分策略

    Returns:
        score: 分数值
    """
    if strategy == MINAREA:
        return rect.w * rect.h  # 使用面积作为评分

    return 0


def split_free_rectangle(free_rectangles, free_rect, used_rect, free_rect_idx):
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
    if used_rect.x + used_rect.w != free_rect.x + free_rect.w:
        right = Rectangle(
            used_rect.x + used_rect.w,
            free_rect.y,
            free_rect.x + free_rect.w - (used_rect.x + used_rect.w),
            free_rect.h,
        )

    # 检查下方是否还有剩余空间
    if used_rect.y + used_rect.h != free_rect.y + free_rect.h:
        bottom = Rectangle(
            used_rect.x,
            used_rect.y + used_rect.h,
            used_rect.w,
            free_rect.y + free_rect.h - (used_rect.y + used_rect.h),
        )

    # 处理分割后的区域
    if right and bottom:
        # 调整区域边界避免重叠
        if right.w * right.h < free_rect.w * bottom.h:
            right, bottom = Rectangle(
                right.x,
                right.y,
                right.w,
                right.h - (bottom.h),
            ), Rectangle(bottom.x, bottom.y, free_rect.w, bottom.h)

        # 更新空闲区域列表
        free_rectangles[free_rect_idx] = right
        free_rectangles.append(bottom)
    elif right:
        free_rectangles[free_rect_idx] = right
    elif bottom:
        free_rectangles[free_rect_idx] = bottom
    else:
        free_rectangles[free_rect_idx] = Rectangle(
            0,
            0,
            0,
            0,
        )


def merge_free_rectangles(rectangles):
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
                merged_rect = try_merge_rectangles(rectangles[i], rectangles[j])

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


def find_position(free_rectangles, width, height, min_rectangle):
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
    invalid_rectangles = []
    best_score = float("inf")  # 最佳分数（越小越好）
    best_rect = None
    in_free_rect = None
    in_free_rect_idx = None

    # 遍历所有空闲区域
    for free_rect in free_rectangles:
        # 删除过小的空闲区域
        if (
            free_rect == "removed"
            or free_rect.w < min_rectangle[1]
            or free_rect.h < min_rectangle[2]
        ):
            invalid_rectangles.append(free_rect)
            continue

        # 跳过无法容纳当前矩形的区域
        if free_rect.w < width or free_rect.h < height:
            new_free_rectangles.append(free_rect)
            continue

        # 计算当前空闲区域的分数
        score = calculate_score(free_rect, MINAREA)

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
    free_rectangles = new_free_rectangles

    if best_rect:
        return free_rectangles, (best_rect, in_free_rect, in_free_rect_idx)

    return free_rectangles, None


def fit(rectangles, width, height):
    """
    使用MaxRects算法排列矩形

    Args:
        rectangles: 待排列的矩形列表，格式为[(id, width, height), ...]

    Returns:
        results: 排列结果列表，格式为[(rect_id, Rectangle), ...]
    """
    border = setting["border"]
    results = []
    used_rectangles = []
    free_rectangles = [Rectangle(border, border, width - border, height - border)]

    # 获取最小的矩形（用于优化判断）
    min_rectangle = rectangles[-1]

    # 遍历所有矩形进行排列
    for rect_id, w, h in rectangles:
        rect = in_free_rect = free_rect_idx = None

        # 寻找最佳放置位置
        free_rectangles, rect_data = find_position(free_rectangles, w, h, min_rectangle)

        if rect_data:
            rect, in_free_rect, free_rect_idx = rect_data

            # 分割剩余空间
            split_free_rectangle(free_rectangles, in_free_rect, rect, free_rect_idx)

            # 合并相邻的空闲区域
            free_rectangles = merge_free_rectangles(free_rectangles)

            # 记录已使用的矩形
            used_rectangles.append(rect)
            results.append((rect_id, rect))

    return results


def maxrects_packing(rectangles, atlas_size):
    """
    使用MaxRects算法进行排列

    Args:
        rectangles: 矩形数据列表
        atlas_size: 图集尺寸 (width, height)
        idx: 图集索引
    """
    # 执行排列算法
    results = fit(rectangles, atlas_size.x, atlas_size.y)

    return results


def simulate_packing_efficiency(rectangles, size):
    """
    模拟排列并计算空间利用率

    Args:
        rectangles: 矩形数据列表
        size: 模拟大小

    Returns:
        efficiency: 空间利用率 (0-1)
        remaining_rect: 无法排列的矩形列表
    """
    # 创建临时打包器进行模拟
    results = fit(rectangles, size.x, size.y)

    return results


def calculate_optimal_size(rectangles, images):
    """
    计算最优的图集尺寸

    Args:
        rectangles: 矩形数据列表
        idx: 图集索引

    Returns:
        best_size: 最佳尺寸 (width, height)
        remaining_rect: 剩余未排列的矩形
    """
    remaining_rect = is_several_atlas = last_size = last_efficiency = (
        last_remaining_rect
    ) = None

    # 尝试的尺寸序列
    sizes = setting["sizes"]

    sizes = [Vector(s[0], s[1], int) for s in sizes]

    best_size = sizes[0]

    # 遍历尺寸寻找最佳匹配
    for size in sizes:
        is_first = size == sizes[0]
        is_end = size == sizes[-1]

        # 模拟打包并计算利用率
        results = simulate_packing_efficiency(rectangles, size)

        if len(results) < len(rectangles):
            remaining_rect = [
                rect
                for rect in rectangles
                if rect[0] not in set([r[0] for r in results])
            ]

            if is_end:
                best_size = size
                is_several_atlas = True
                break

            continue

        used_area = sum(img[1].w * img[1].h for img in results)
        total_area = size.x * size.y

        efficiency = used_area / total_area

        # 利用率较低使用多图集打包
        if 0 < efficiency < setting["trigger_several_efficiency"]:
            if is_first:
                best_size = size
            else:
                best_size = last_size
                is_several_atlas = True

                efficiency, remaining_rect = last_efficiency, last_remaining_rect
            break
        # 利用率可接受，使用当前尺寸
        elif efficiency > setting["trigger_several_efficiency"]:
            best_size = size
            break

        last_size = size
        last_efficiency, last_remaining_rect = efficiency, remaining_rect

    return best_size, remaining_rect, is_several_atlas


def create_atlas(baisic_atlas_name, rectangles, images):
    """
    创建图集

    Args:
        rectangles: 矩形数据列表
        idx: 图集索引（用于多图集情况）
    """
    is_several_atlas = True
    idx = 1
    finish_results = []

    while is_several_atlas:
        atlas_name = baisic_atlas_name + f"-{idx}"

        atlas_size, remaining_rect, is_several_atlas = calculate_optimal_size(
            rectangles, images
        )

        print(f"🏁 计算{atlas_name}尺寸: {atlas_size.x}x{atlas_size.y}")

        # 使用MaxRects算法进行排列
        results = maxrects_packing(rectangles, atlas_size)

        # 记录打包结果
        finish_results.append(
            {
                "name": atlas_name,
                "rectangles_id": sorted([rect[0] for rect in results]),
                "atlas_size": atlas_size,
            }
        )

        # 转换结果为实际位置信息
        for rect_id, rect in results:
            images[rect_id]["pos"] = Vector(rect.x, rect.y, int)

        rectangles = remaining_rect

        idx += 1

    return finish_results


def write_atlas(images, result):
    """
    创建并保存图集图片

    Args:
        result: 打包结果数据
    """
    # 创建空白图集
    with Image.new(
        "RGBA", (result["atlas_size"].x, result["atlas_size"].y), (0, 0, 0, 0)
    ) as atlas:
        output_file = config.output_path / f"{result["name"]}.png"

        # 将所有图片粘贴到图集上
        for img_id in result["rectangles_id"]:
            img_info = images[img_id]
            img_pos = img_info["pos"]

            if img_pos:
                position = (img_pos.x, img_pos.y)
                atlas.paste(img_info["image"], position)

        # 在左上角添加白色像素（可能用于特殊用途，如血条）
        if setting["add_white_rect"]:
            draw = ImageDraw.Draw(atlas)
            ww, wh = setting["white_rect_size"]
            draw.rectangle([0, 0, ww, wh], "white", None, 0)

        # 保存PNG文件
        atlas.save(output_file)

        # 转换为DDS格式
        if setting["output_format"] == "bc7" or setting["output_format"] == "bc3":
            save_to_dds(
                output_file,
                config.output_path,
                setting["output_format"],
                setting["delete_temporary_png"],
            )
        elif setting["output_format"] == "png":
            print(f"✅ 保存为png: {output_file.name}...")


def write_lua_data(images, results, atlas_name):
    """生成Lua格式的图集数据文件"""
    content = [
        "return {",
    ]

    def a(str):
        content.append(str)

    # 遍历所有打包结果
    for result in results:
        for i, img_id in enumerate(result["rectangles_id"]):
            img = images[img_id]
            pos = img["pos"]
            trim = img["trim"]

            # 写入图片数据
            if is_simple_key(img["name"]):
                a(f"\t{img["name"]} = {{")
            else:
                a(f'\t["{img["name"]}"] = {{')

            if setting["output_format"] == "png":
                a(f'\t\ta_name = "{result["name"]}.png",')
            else:
                a(f'\t\ta_name = "{result["name"]}.dds",')

            # 原始尺寸
            a(f"\t\tsize = {{")
            a(f"\t\t\t{img["origin_width"]},")
            a(f"\t\t\t{img["origin_height"]}")
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
            a(f"\t\t\t{result["atlas_size"].x},")
            a(f"\t\t\t{result["atlas_size"].y}")
            a("\t\t},")

            # 在图集中的位置和尺寸
            a("\t\tf_quad = {")
            a(f"\t\t\t{pos.x},")
            a(f"\t\t\t{pos.y},")
            a(f"\t\t\t{img["width"]},")
            a(f"\t\t\t{img["height"]}")
            a("\t\t},")

            # 相同图片别名
            if len(img["samed_img"]) > 0:
                a("\t\talias = {")
                for i, name in enumerate(img["samed_img"]):
                    if i < len(img["samed_img"]) - 1:
                        a(f'\t\t\t"{name}",')
                    else:
                        a(f'\t\t\t"{name}"')
                a("\t\t}")
            else:
                a("\t\talias = {}")

            # 结束当前图片数据
            if i < len(result["rectangles_id"]) - 1:
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
        new_img: 裁剪后的图片
        trim_data: 调整后的裁剪信息
    """
    origin_width = img.width
    origin_height = img.height

    left = top = right = bottom = 0

    # 获取Alpha通道
    if img.mode == "RGB":
        img = img.convert("RGBA")

    alpha = img.getchannel("A")

    # 获取非透明区域的边界框
    bbox = alpha.getbbox()
    if bbox:
        left, top, right, bottom = bbox

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
        input_subdir: 按子目录组织的图片数据字典
    """
    input_subdir = {}

    # 遍历输入目录下的所有子目录
    for item in config.input_path.iterdir():
        hash_groups = {}  # 用于检测重复图片
        # 遍历子目录中的所有图片文件
        if not item.is_dir():
            continue

        input_subdir[item.name] = {"images": [], "rectangles": []}
        images = input_subdir[item.name]["images"]

        for image_file in item.iterdir():
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
                new_img, trim = process_img(img)

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

                print(
                    f"📖 加载图片  {image_file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                )

            padding = setting["padding"]

            # 准备矩形数据用于打包 (id, width, height)
            rectangles = [
                (i, img["width"] + padding, img["height"] + padding)
                for i, img in enumerate(images)
            ]

            # 按面积降序排列
            input_subdir[item.name]["rectangles"] = sorted(
                rectangles, key=lambda r: r[1] * r[2], reverse=True
            )

    return input_subdir


def main():
    """主函数：执行图集生成流程"""
    # 加载并处理输入图片
    input_subdir = get_input_subdir()

    print("所有图片加载完毕\n")

    if not input_subdir:
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
            write_atlas(images, result)

        write_lua_data(images, results, atlas_stem_name)

        print(f"{atlas_stem_name}图集生成完毕\n")

        # 释放图片资源
        for img_info in images:
            img_info["image"].close()

    print("所有图集生成完毕")
