import traceback, subprocess, time, config, re
from pathlib import Path
import numpy as np
import log

log = log.setup_logging(config.log_level, config.log_file)

input_path = config.input_path
output_path = config.output_path


def clamp(value, min_value, max_value):
    """将值限制在[min_value, max_value]范围内"""
    return max(min_value, min(value, max_value))


def run_decompiler(file_path, output_path="output"):
    """反编译lua文件"""
    result = subprocess.run(
        [
            "luajit-decompiler-v2.exe",
            str(file_path),
            "-s",  # 禁用错误弹窗
            "-f",  # 始终替换
            "-o",
            str(output_path),  # 输出目录
        ],
        capture_output=True,
        text=True,
    )

    return result


def save_to_dds(target_file, output_path, bc, delete_temporary_png=False):
    """
    将PNG图片转换为DDS格式

    Args:
        output_file: 输出文件路径
        bc: BC压缩格式 (1-7)
    """
    all_bc = {
        "bc3": "BC3",
        "bc7": "BC7",
    }

    bc = all_bc[bc]

    log.info(f"✅ 保存为DDS {bc}格式: {target_file.stem}.dds...")

    output_format = f"{bc}_UNORM"

    result = subprocess.run(
        [
            "texconv.exe",
            "-f",
            output_format,  # BC格式
            "-y",  # 覆盖已存在文件
            "-o",
            output_path,
            target_file,
        ],
        capture_output=True,
        text=True,
    )

    # 删除临时PNG文件
    if delete_temporary_png:
        Path(target_file).unlink()
        f"🗑️ 已删除临时PNG文件: {target_file.name}"

    return result


def is_simple_key(key: str):
    """检查键名是否为简单标识符（只包含字母、数字、下划线，不以数字开头）"""
    if not key or key[0].isdigit():
        return False
    return all(c.isalnum() or c == "_" for c in key)

find_num_regex = r"[-+]?\d*\.?\d+"
class Point:

    def __init__(self, x=None, y=None, str_format=None):
        if str_format:
            numbers = re.findall(find_num_regex, str_format)
            if len(numbers) >= 2:
                self.x = float(numbers[0])
                self.y = float(numbers[1])
            return
        
        self.x = x
        self.y = y

    def __iter__(self):
        yield self.x
        yield self.y

    def __str__(self):
        return "{%s, %s}" % (self.x, self.y)

    def copy(self):
        return Point(self.x, self.y)
    
    def map(self, func):
        return func(self.x, self.y)


class Size:

    def __init__(self, w=None, h=None, str_format=None):
        if str_format:
            numbers = re.findall(find_num_regex, str_format)
            if len(numbers) >= 2:
                self.w = float(numbers[0])
                self.h = float(numbers[1])
            return

        self.w = w
        self.h = h

    def __iter__(self):
        yield self.w
        yield self.h

    def __str__(self):
        return "{%s, %s}" % (self.w, self.h)

    def copy(self):
        return Size(self.w, self.h)

    def map(self, func):
        return func(self.w, self.h)


class Rectangle:
    """向量类"""

    def __init__(self, x=None, y=None, w=None, h=None, str_format=None):
        if str_format:
            numbers = re.findall(find_num_regex, str_format)
            if len(numbers) == 4:
                self.x = float(numbers[0])
                self.y = float(numbers[1])
                self.w = float(numbers[2])
                self.h = float(numbers[3])
            return

        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.w
        yield self.h

    def __str__(self):
        return "{{%s, %s}, {%s, %s}}" % (self.x, self.y, self.w, self.h)

    def copy(self):
        return Rectangle(self.x, self.y, self.w, self.h)

    def map(self, func):
        return func(self.x, self.y, self.w, self.h)

    def other_pos(self, other: "Rectangle") -> list[str]:
        """返回另一个矩形相当于当前矩形的位置"""
        pos = []

        if self.x + self.w <= other.x:
            pos.append("right")
        elif self.x >= other.x:
            pos.append("left")

        if self.y + self.h <= other.y:
            pos.append("top")
        elif self.y >= other.y:
            pos.append("bottom")

        if not pos:
            pos.append("in")

        return pos


class Bounds:

    def __init__(self, left=None, top=None, right=None, bottom=None, str_format=None):
        if str_format:
            numbers = re.findall(find_num_regex, str_format)
            if len(numbers) == 4:
                self.left = float(numbers[0])
                self.top = float(numbers[1])
                self.right = float(numbers[2])
                self.bottom = float(numbers[3])
            return

        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def __iter__(self):
        yield self.left
        yield self.top
        yield self.right
        yield self.bottom

    def __str__(self):
        return "{{%s, %s}, {%s, %s}}" % (self.left, self.top, self.right, self.bottom)

    def copy(self):
        return Bounds(self.left, self.top, self.right, self.bottom)

    def map(self, func):
        return func(self.left, self.top, self.right, self.bottom)
