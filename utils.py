import traceback, subprocess, time, config, re
from pathlib import Path
import numpy as np
import log

log = log.setup_logging(config.log_level, config.log_file)

input_path = config.input_path
output_path = config.output_path


def clamp(value, min_value, max_value):
    """
    将数值限制在指定范围内

    如果value小于min_value，返回min_value；
    如果value大于max_value，返回max_value；
    否则返回原值。

    Args:
        value (float/int): 需要限制的值
        min_value (float/int): 最小值
        max_value (float/int): 最大值

    Returns:
        float/int: 限制后的值

    Examples:
        >>> clamp(10, 0, 5)
        5
        >>> clamp(-1, 0, 5)
        0
        >>> clamp(3, 0, 5)
        3
    """
    return max(min_value, min(value, max_value))


def run_decompiler(file_path, output_path="output"):
    """
    使用luajit-decompiler工具反编译Lua文件

    Args:
        file_path (Path/str): 要反编译的Lua文件路径
        output_path (str, optional): 反编译后的输出目录，默认为"output"

    Returns:
        subprocess.CompletedProcess: 包含反编译执行结果的CompletedProcess对象
            - returncode: 返回码（0表示成功）
            - stdout: 标准输出内容
            - stderr: 标准错误内容

    Note:
        需要确保luajit-decompiler-v2.exe在系统路径中或当前目录下可用
    """
    result = subprocess.run(
        [
            "luajit-decompiler-v2.exe",  # Lua反编译器可执行文件
            str(file_path),  # 要反编译的文件路径
            "-s",  # 禁用错误弹窗（silent模式）
            "-f",  # 始终替换已存在的输出文件
            "-o",
            str(output_path),  # 输出目录
        ],
        capture_output=True,  # 捕获标准输出和错误输出
        text=True,  # 以文本模式返回输出
    )

    return result


def save_to_dds(target_file, output_path, bc, delete_temporary_png=False):
    """
    使用texconv工具将PNG图片转换为DDS格式

    Args:
        target_file (Path/str): 要转换的PNG图片文件路径
        output_path (Path/str): DDS文件输出目录
        bc (str): BC压缩格式，支持"bc3"或"bc7"
            - "bc3": DXT5压缩，支持Alpha通道
            - "bc7": 高质量的BC压缩格式，支持更好的质量
        delete_temporary_png (bool, optional): 转换后是否删除临时PNG文件，默认为False

    Returns:
        subprocess.CompletedProcess: 包含转换执行结果的CompletedProcess对象

    Raises:
        KeyError: 如果传入的bc参数不是有效的压缩格式

    Note:
        需要确保texconv.exe在系统路径中或当前目录下可用
        此函数主要用于游戏资源处理中纹理格式转换
    """
    # BC格式映射表
    all_bc = {
        "bc3": "BC3",  # 对应DXT5格式
        "bc7": "BC7",  # 高质量压缩格式
    }

    # 获取对应的BC格式字符串
    bc = all_bc[bc]

    log.info(f"✅ 保存为DDS {bc}格式: {target_file.stem}.dds...")

    # 设置输出格式
    output_format = f"{bc}_UNORM"  # 无符号归一化格式

    # 执行texconv转换命令
    result = subprocess.run(
        [
            "texconv.exe",  # DirectX纹理转换工具
            "-f",
            output_format,  # 指定输出格式
            "-y",  # 覆盖已存在的文件
            "-o",
            output_path,  # 输出目录
            target_file,  # 输入文件
        ],
        capture_output=True,  # 捕获输出
        text=True,  # 以文本模式处理输出
    )

    # 可选：删除临时PNG文件
    if delete_temporary_png:
        png_file = Path(target_file)
        if png_file.exists():
            png_file.unlink()
            log.info(f"🗑️ 已删除临时PNG文件: {png_file.name}")

    return result


def is_simple_key(key: str):
    """
    检查字符串是否为简单的标识符（符合编程语言变量命名规范）

    简单标识符的规则：
    1. 不能为空
    2. 第一个字符不能是数字
    3. 只能包含字母、数字和下划线

    Args:
        key (str): 要检查的键名字符串

    Returns:
        bool: 如果是简单标识符返回True，否则返回False

    Examples:
        >>> is_simple_key("player_name")
        True
        >>> is_simple_key("123abc")
        False
        >>> is_simple_key("item-price")
        False
        >>> is_simple_key("")
        False
    """
    if not key or key[0].isdigit():
        return False
    return all(c.isalnum() or c == "_" for c in key)


# 正则表达式：用于从字符串中提取数字（包括整数、小数和带符号的数字）
find_num_regex = r"[-+]?\d*\.?\d+"


class Point:
    """
    二维点类，表示一个二维坐标点(x, y)

    支持多种初始化方式：
    1. 直接传入x, y坐标
    2. 从字符串格式如"{x, y}"中解析

    Attributes:
        x (float): X坐标
        y (float): Y坐标

    Methods:
        __iter__: 使对象可迭代，返回(x, y)
        __str__: 返回格式化字符串"{x, y}"
        copy: 创建点的副本
        map: 对x, y坐标应用函数
    """

    def __init__(self, x=None, y=None, str_format=None):
        """
        初始化Point对象

        Args:
            x (float, optional): X坐标值
            y (float, optional): Y坐标值
            str_format (str, optional): 格式为"{x, y}"的字符串

        Note:
            如果提供了str_format，将优先从字符串解析，忽略x和y参数
        """
        if str_format:
            # 从字符串中提取数字
            numbers = re.findall(find_num_regex, str_format)
            if len(numbers) >= 2:
                self.x = float(numbers[0])
                self.y = float(numbers[1])
            return

        self.x = x
        self.y = y

    def __iter__(self):
        """
        使Point对象可迭代

        Returns:
            generator: 依次生成x, y坐标

        Example:
            >>> p = Point(1, 2)
            >>> for coord in p:
            ...     print(coord)
            1
            2
        """
        yield self.x
        yield self.y

    def __str__(self):
        """
        返回点的字符串表示

        Returns:
            str: 格式为"{x, y}"的字符串

        Example:
            >>> str(Point(1.5, 2.5))
            '{1.5, 2.5}'
        """
        return "{%s, %s}" % (self.x, self.y)

    def copy(self):
        """
        创建点的深拷贝

        Returns:
            Point: 新的Point对象，包含相同的坐标值
        """
        return Point(self.x, self.y)

    def map(self, func):
        """
        对x, y坐标应用函数

        Args:
            func (callable): 接受两个参数的函数

        Returns:
            函数func的返回值

        Example:
            >>> p = Point(1, 2)
            >>> p.map(lambda x, y: x + y)
            3
        """
        return func(self.x, self.y)


class Size:
    """
    尺寸类，表示二维尺寸(width, height)

    Attributes:
        w (float): 宽度
        h (float): 高度

    Methods:
        __iter__: 使对象可迭代，返回(w, h)
        __str__: 返回格式化字符串"{w, h}"
        copy: 创建尺寸的副本
        map: 对宽度和高度应用函数
    """

    def __init__(self, w=None, h=None, str_format=None):
        """
        初始化Size对象

        Args:
            w (float, optional): 宽度
            h (float, optional): 高度
            str_format (str, optional): 格式为"{w, h}"的字符串
        """
        if str_format:
            # 从字符串中提取数字
            numbers = re.findall(find_num_regex, str_format)
            if len(numbers) >= 2:
                self.w = float(numbers[0])
                self.h = float(numbers[1])
            return

        self.w = w
        self.h = h

    def __iter__(self):
        """
        使Size对象可迭代

        Returns:
            generator: 依次生成宽度和高度
        """
        yield self.w
        yield self.h

    def __str__(self):
        """
        返回尺寸的字符串表示

        Returns:
            str: 格式为"{w, h}"的字符串
        """
        return "{%s, %s}" % (self.w, self.h)

    def copy(self):
        """
        创建尺寸的深拷贝

        Returns:
            Size: 新的Size对象，包含相同的宽度和高度
        """
        return Size(self.w, self.h)

    def map(self, func):
        """
        对宽度和高度应用函数

        Args:
            func (callable): 接受两个参数的函数

        Returns:
            函数func的返回值
        """
        return func(self.w, self.h)


class Rectangle:
    """
    矩形类，表示一个二维矩形区域

    矩形由左上角坐标(x, y)和尺寸(w, h)定义：
    - x: 矩形左上角的X坐标
    - y: 矩形左上角的Y坐标
    - w: 矩形的宽度
    - h: 矩形的高度

    Methods:
        __iter__: 使对象可迭代，返回(x, y, w, h)
        __str__: 返回格式化字符串"{{x, y}, {w, h}}"
        copy: 创建矩形的副本
        map: 对矩形的四个属性应用函数
        other_pos: 判断另一个矩形相对于当前矩形的位置
    """

    def __init__(self, x=None, y=None, w=None, h=None, str_format=None):
        """
        初始化Rectangle对象

        Args:
            x (float, optional): 左上角X坐标
            y (float, optional): 左上角Y坐标
            w (float, optional): 宽度
            h (float, optional): 高度
            str_format (str, optional): 格式为"{{x, y}, {w, h}}"的字符串
        """
        if str_format:
            # 从字符串中提取数字
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
        """
        使Rectangle对象可迭代

        Returns:
            generator: 依次生成x, y, w, h

        Example:
            >>> rect = Rectangle(0, 0, 100, 50)
            >>> list(rect)
            [0, 0, 100, 50]
        """
        yield self.x
        yield self.y
        yield self.w
        yield self.h

    def __str__(self):
        """
        返回矩形的字符串表示

        Returns:
            str: 格式为"{{x, y}, {w, h}}"的字符串
        """
        return "{{%s, %s}, {%s, %s}}" % (self.x, self.y, self.w, self.h)

    def copy(self):
        """
        创建矩形的深拷贝

        Returns:
            Rectangle: 新的Rectangle对象，包含相同的属性值
        """
        return Rectangle(self.x, self.y, self.w, self.h)

    def map(self, func):
        """
        对矩形的四个属性应用函数

        Args:
            func (callable): 接受四个参数的函数

        Returns:
            函数func的返回值
        """
        return func(self.x, self.y, self.w, self.h)

    def other_pos(self, other: "Rectangle") -> list[str]:
        """
        判断另一个矩形相对于当前矩形的位置关系

        位置关系可能包括：
        - "left": 在左侧
        - "right": 在右侧
        - "top": 在上方
        - "bottom": 在下方
        - "in": 相交或包含

        Args:
            other (Rectangle): 另一个矩形对象

        Returns:
            list[str]: 位置描述字符串列表

        Example:
            >>> rect1 = Rectangle(0, 0, 100, 100)
            >>> rect2 = Rectangle(150, 50, 50, 50)
            >>> rect1.other_pos(rect2)
            ['right']

            >>> rect3 = Rectangle(50, 50, 25, 25)
            >>> rect1.other_pos(rect3)
            ['in']
        """
        pos = []

        # 判断左右关系
        if self.x + self.w <= other.x:
            pos.append("right")  # 当前矩形完全在other矩形左侧
        elif self.x >= other.x:
            pos.append("left")  # 当前矩形完全在other矩形右侧

        # 判断上下关系
        if self.y + self.h <= other.y:
            pos.append("top")  # 当前矩形完全在other矩形下方
        elif self.y >= other.y:
            pos.append("bottom")  # 当前矩形完全在other矩形上方

        # 如果没有任何方向关系，说明矩形相交或包含
        if not pos:
            pos.append("in")

        return pos


class Bounds:
    """
    边界类，表示一个矩形的四条边界

    与Rectangle不同，Bounds用四条边界的坐标定义：
    - left: 左边界X坐标
    - top: 上边界Y坐标
    - right: 右边界X坐标
    - bottom: 下边界Y坐标

    这通常用于UI布局和碰撞检测中。
    """

    def __init__(self, left=None, top=None, right=None, bottom=None, str_format=None):
        """
        初始化Bounds对象

        Args:
            left (float, optional): 左边界坐标
            top (float, optional): 上边界坐标
            right (float, optional): 右边界坐标
            bottom (float, optional): 下边界坐标
            str_format (str, optional): 格式为"{{left, top}, {right, bottom}}"的字符串
        """
        if str_format:
            # 从字符串中提取数字
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
        """
        使Bounds对象可迭代

        Returns:
            generator: 依次生成left, top, right, bottom
        """
        yield self.left
        yield self.top
        yield self.right
        yield self.bottom

    def __str__(self):
        """
        返回边界的字符串表示

        Returns:
            str: 格式为"{{left, top}, {right, bottom}}"的字符串
        """
        return "{{%s, %s}, {%s, %s}}" % (self.left, self.top, self.right, self.bottom)

    def copy(self):
        """
        创建边界的深拷贝

        Returns:
            Bounds: 新的Bounds对象，包含相同的边界值
        """
        return Bounds(self.left, self.top, self.right, self.bottom)

    def map(self, func):
        """
        对四条边界坐标应用函数

        Args:
            func (callable): 接受四个参数的函数

        Returns:
            函数func的返回值
        """
        return func(self.left, self.top, self.right, self.bottom)
