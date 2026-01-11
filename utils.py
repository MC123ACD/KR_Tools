import traceback, subprocess, time, config, re
from pathlib import Path
from abc import ABC, ABCMeta
from typing import ClassVar, TypeVar, Generic, Any
import log

log = log.setup_logging(config.log_level, config.log_file)

input_path = config.input_path
output_path = config.output_path


T = TypeVar("T")

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
FIND_NUM_REGEX = r"[-+]?\d*\.?\d+"


class FieldMeta(ABCMeta):
    """元类，自动生成__init__方法"""

    def __new__(cls, name, bases, attrs):
        if "fields" in attrs:
            fields = attrs["fields"]

            # 自动生成__init__方法
            def auto_init(self, *args, **kwargs):
                str_format = kwargs.get("str_format") if kwargs else None
                if str_format:
                    numbers = re.findall(FIND_NUM_REGEX, str_format)
                    for i, field in enumerate(fields):
                        if i < len(numbers):
                            setattr(self, field, float(numbers[i]))
                else:
                    for i, field in enumerate(fields):
                        if i < len(args):
                            setattr(self, field, args[i])
                        elif field in kwargs:
                            setattr(self, field, kwargs[field])
                        else:
                            setattr(self, field, None)

            attrs["__init__"] = auto_init
        return super().__new__(cls, name, bases, attrs)


class GeometryBase(ABC, metaclass=FieldMeta):
    """几何对象的基类"""

    fields: ClassVar[tuple]  # 子类必须定义

    def __init_subclass__(cls, **kwargs):
        """确保子类定义了fields"""
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "fields"):
            raise TypeError(f"{cls.__name__} must define 'fields' class variable")

    def __iter__(self):
        """使对象可迭代"""
        for field in self.fields:
            yield getattr(self, field)

    def __hash__(self):
        """基于所有字段计算哈希值"""
        return hash(tuple(getattr(self, field) for field in self.fields))

    def __eq__(self, other):
        """比较两个对象是否相等"""
        if type(self) != type(other):
            return False
        return all(
            getattr(self, field) == getattr(other, field) for field in self.fields
        )

    def __repr__(self):
        """开发者友好的表示"""
        fields_str = ", ".join(
            f"{field}={getattr(self, field)}" for field in self.fields
        )
        return f"{self.__class__.__name__}({fields_str})"

    def __str__(self):
        """用户友好的字符串表示"""
        return "{%s}" % (", ".join(str(getattr(self, field)) for field in self.fields))

    def to_int(self):
        """当调用 int(size_obj) 时调用"""
        return type(self)(**{field: int(getattr(self, field)) for field in self.fields})

    def to_float(self):
        """当调用 int(size_obj) 时调用"""
        return type(self)(**{field: float(getattr(self, field)) for field in self.fields})

    def copy(self):
        """创建副本"""
        return type(self)(**{field: getattr(self, field) for field in self.fields})

    def map(self, func):
        """对字段应用函数"""
        return func(*(getattr(self, field) for field in self.fields))


# 使用基类定义具体类
class Point(GeometryBase):
    """二维点类"""

    fields = ("x", "y")

    def __str__(self):
        """重写以使用花括号格式"""
        return "{%s, %s}" % (self.x, self.y)


class Size(GeometryBase):
    """尺寸类"""

    fields = ("w", "h")

    def __str__(self):
        """重写以使用花括号格式"""
        return "{%s, %s}" % (self.w, self.h)

    def scale(self, factor):
        """缩放"""
        return Size(self.w * factor, self.h * factor)

    def area(self):
        """面积"""
        return self.w * self.h

    def perimeter(self):
        """周长"""
        return 2 * (self.w + self.h)

    def is_congruent(self, other):
        """大小相同"""
        if not isinstance(other, Rectangle):
            return False
        return self.w == other.w and self.h == other.h


class Rectangle(GeometryBase):
    """矩形类"""

    fields = ("x", "y", "w", "h")

    def __str__(self):
        """重写以使用嵌套花括号格式"""
        return "{{%s, %s}, {%s, %s}}" % (self.x, self.y, self.w, self.h)

    def scale(self, factor):
        """缩放"""
        return Rectangle(self.x, self.y, self.w * factor, self.h * factor)

    def area(self):
        """面积"""
        return self.w * self.h

    def perimeter(self):
        """周长"""
        return 2 * (self.w + self.h)

    def is_congruent(self, other):
        """大小相同"""
        if not isinstance(other, Rectangle):
            return False
        return self.w == other.w and self.h == other.h

    def is_identical(self, other):
        """完全相同的矩形（位置和大小都相同）"""
        if not isinstance(other, Rectangle):
            return False
        return (
            self.x == other.x
            and self.y == other.y
            and self.w == other.w
            and self.h == other.h
        )

    def other_position(self, other: "Rectangle") -> list[str]:
        """判断另一个矩形相对于当前矩形的位置关系"""
        relations = set()

        # 判断左右关系
        if self.x + self.w <= other.x:
            relations.add("right")  # 当前矩形完全在other矩形左侧
        elif self.x >= other.x:
            relations.add("left")  # 当前矩形完全在other矩形右侧

        # 判断上下关系
        if self.y + self.h <= other.y:
            relations.add("bottom")  # 当前矩形完全在other矩形下方
        elif self.y >= other.y:
            relations.add("top")  # 当前矩形完全在other矩形上方

        # 如果没有任何方向关系，说明矩形相交或包含
        if not relations:
            relations.add("in")

        return relations


class Bounds(GeometryBase):
    """边界类"""

    fields = ("left", "top", "right", "bottom")

    def __str__(self):
        """重写以使用嵌套花括号格式"""
        return "{{%s, %s}, {%s, %s}}" % (self.left, self.top, self.right, self.bottom)
