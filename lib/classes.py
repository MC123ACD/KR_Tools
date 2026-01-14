import traceback, subprocess, time, lib.config as config, re
from lib.utils import key_to_lua, value_to_lua
from lib.constants import FIND_NUM_REGEX
from pathlib import Path
from abc import ABC, ABCMeta
from typing import ClassVar
import lib.log as log

# 初始化日志系统，使用配置文件中的日志级别和日志文件路径
log = log.setup_logging(config.log_level, config.log_file)

class WriteLua:
    def __init__(self, init_content=None):
        self.content_list = init_content if init_content is not None else []
        self.indent_char = "\t"

    def add_line(self, indent_level=0, content="", comment=""):
        """添加一行内容"""
        line = self.indent_char * indent_level + str(content)
        if comment:
            line += f"  -- {comment}"
        self.content_list.append(line)
        return self  # 支持链式调用

    def add_start(self, indent_level=0, key=None, comment=""):
        """添加开始"""
        if key:
            self.add_line(indent_level, f"{key_to_lua(key)} = {{", comment)
        else:
            self.add_line(indent_level, "{", comment)
        return self

    def add_end(self, indent_level=0, with_comma=True):
        """添加结束"""
        self.content_list[-1] = re.sub(r",$", "", self.content_list[-1])
        line = "}" + ("," if with_comma else "")

        self.add_line(indent_level, line)
        return self

    def add_dict_v(self, indent_level=0, key=None, value=None, comment=""):
        """添加键值对"""
        line = f"{key_to_lua(key)} = {value_to_lua(value)}" + ","
        self.add_line(indent_level, line, comment)
        return self

    def add_list_v(self, indent_level=0, value=None, comment=""):
        """添加值"""
        line = value_to_lua(value) + ","
        self.add_line(indent_level, line, comment)
        return self

    def get_content(self):
        """获取完整内容"""
        return "\n".join(self.content_list)

    def clear(self):
        """清空内容"""
        self.content_list.clear()
        return self

    def get_helpers(self):
        """返回一组辅助函数"""
        return [
            self.add_line,
            self.add_start,
            self.add_end,
            self.add_dict_v,
            self.add_list_v,
        ]

    # def generate_lua_content(self):


class FieldMeta(ABCMeta):
    """元类，自动生成__init__方法"""

    def __new__(cls, name, bases, attrs):
        if "fields" in attrs:
            fields = attrs["fields"]

            # 自动生成__init__方法
            def auto_init(self, *args, **kwargs):
                if not args and not kwargs:
                    raise TypeError(
                        f"Cannot instantiate {cls.__name__} without positional arguments. "
                        f"Please provide required positional parameters."
                    )

                if args:
                    first_arg = args[0]

                    if isinstance(first_arg, str):
                        numbers = re.findall(FIND_NUM_REGEX, first_arg)
                        for i, field in enumerate(fields):
                            if i < len(numbers):
                                setattr(self, field, int(float(numbers[i])))

                        return
                    elif isinstance(first_arg, (list, tuple)):
                        first_arg_len = len(first_arg)
                        fields_len = len(fields)
                        if first_arg_len != fields_len:
                            raise TypeError(
                                f"{cls.__name__}() requires {fields_len} values in the sequence, "
                                f"but got {first_arg_len}"
                            )
                        for i, a in enumerate(first_arg):
                            setattr(self, fields[i], a)

                        return

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
        return type(self)(
            **{field: float(getattr(self, field)) for field in self.fields}
        )

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
