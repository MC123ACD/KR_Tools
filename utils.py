import traceback, subprocess, time, config
from pathlib import Path
import numpy as np

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

    print(f"✅ 保存为DDS {bc}格式: {target_file.stem}.dds...")

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


import numpy as np
from typing import Union, List


class Vector:
    """向量类"""

    def __init__(self, x, y, type=float, rounding="trunc"):
        """
        Args:
            rounding: 'trunc' - 截断, 'round' - 四舍五入, 'floor' - 向下取整, 'ceil' - 向上取整
        """
        self.rounding = rounding

        if type is int:
            if rounding == "round":
                # 四舍五入
                x, y = [round(v) for v in (x, y)]
            elif rounding == "floor":
                # 向下取整
                x, y = [np.floor(v) for v in (x, y)]
            elif rounding == "ceil":
                # 向上取整
                x, y = [np.ceil(v) for v in (x, y)]
            # 'trunc' 或默认：直接转换，NumPy会截断

            self._data = np.array([x, y], dtype=np.int64)
        elif type is float:
            self._data = np.array([x, y], dtype=np.float64)

    @property
    def x(self) -> float:
        return self._data[0]

    @x.setter
    def x(self, value: float):
        self._data[0] = value

    @property
    def y(self) -> float:
        return self._data[1]

    @y.setter
    def y(self, value: float):
        self._data[1] = value

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(*(self._data + other._data))

    def __sub__(self, other: "Vector") -> "Vector":
        return Vector(*(self._data - other._data))

    def __mul__(self, scalar: float) -> "Vector":
        return Vector(*(self._data * scalar))

    def dot(self, other: "Vector") -> float:
        return np.dot(self._data, other._data)

    def cross(self, other: "Vector") -> "Vector":
        return Vector(*np.cross(self._data, other._data))

    def norm(self) -> float:
        return np.linalg.norm(self._data)

    def normalize(self) -> "Vector":
        norm = self.norm()
        return Vector(*(self._data / norm)) if norm > 0 else Vector()

    def __repr__(self) -> str:
        return f"Vector({self.x:.2f}, {self.y:.2f})"

    def as_array(self) -> np.ndarray:
        """返回底层的NumPy数组（只读视图）"""
        return self._data.view()

    def copy(self) -> "Vector":
        """返回副本"""
        return Vector(*self._data.copy())


class Rectangle:
    """向量类"""

    def __init__(self, x, y, w, h, type=float, rounding="floor"):
        """
        Args:
            rounding: 'trunc' - 截断, 'round' - 四舍五入, 'floor' - 向下取整, 'ceil' - 向上取整
        """
        if type is int:
            if rounding == "round":
                # 四舍五入
                x, y, w, h = [round(v) for v in (x, y, w, h)]
            elif rounding == "floor":
                # 向下取整
                x, y, w, h = [np.floor(v) for v in (x, y, w, h)]
            elif rounding == "ceil":
                # 向上取整
                x, y, w, h = [np.ceil(v) for v in (x, y, w, h)]

            self._data = np.array([x, y, w, h], dtype=np.int64)
        elif type is float:
            self._data = np.array([x, y, w, h], dtype=np.float64)

    @property
    def x(self) -> float:
        return self._data[0]

    @x.setter
    def x(self, value: float):
        self._data[0] = value

    @property
    def y(self) -> float:
        return self._data[1]

    @y.setter
    def y(self, value: float):
        self._data[1] = value

    @property
    def w(self) -> float:
        return self._data[2]

    @w.setter
    def w(self, value: float):
        self._data[2] = value

    @property
    def h(self) -> float:
        return self._data[3]

    @h.setter
    def h(self, value: float):
        self._data[3] = value

    def __repr__(self) -> str:
        return f"Rectangle({self.x:.2f}, {self.y:.2f}, {self.w:.2f}, {self.h:.2f})"

    def as_array(self) -> np.ndarray:
        """返回底层的NumPy数组（只读视图）"""
        return self._data.view()

    def copy(self) -> "Rectangle":
        """返回副本"""
        return Rectangle(*self._data.copy())

    def get_other_pos(self, other: "Rectangle") -> list[str]:
        """返回另一个矩形相当于当前矩形的位置"""
        pos = []

        if self.x + self.w < other.x:
            pos.append("right")
        elif self.x > other.x:
            pos.append("left")

        if self.y + self.h < other.y:
            pos.append("top")
        elif self.y > other.y:
            pos.append("bottom")

        if not pos:
            pos.append("in")

        return pos
