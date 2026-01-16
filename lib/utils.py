import traceback, subprocess, time, re
from pathlib import Path
import tkinter as tk
import lib.config as config
import lib.log as log

log = log.setup_logging(config.log_level, config.log_file)

input_path = config.input_path
output_path = config.output_path


def indent(level):
    """
    生成指定层级的缩进字符串

    使用制表符(\t)进行缩进，每个层级一个制表符。

    Args:
        level (int): 缩进层级，0表示无缩进

    Returns:
        str: 对应层级的缩进字符串

    Examples:
        >>> indent(2)
        '\t\t'
        >>> indent(0)
        ''
    """
    return "\t" * level


def escape_lua_string(s):
    """
    转义Lua字符串中的特殊字符
    """
    if not isinstance(s, str):
        return s

    # 转义特殊字符
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


def run_app(root, app):
    if root:
        root = tk.Toplevel(root)
        app = app(root)
        return
    else:
        root = tk.Tk()
        app = app(root)
        root.mainloop()


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
            "bin/luajit-decompiler-v2.exe",  # Lua反编译器可执行文件
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
            "bin/texconv.exe",  # DirectX纹理转换工具
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


def all_letters_uppercase(s):
    for char in s:
        if char.isalpha() and not char.isupper():
            return False
    return True


def key_to_lua(key):
    key = escape_lua_string(key)

    if key.isdigit():
        return f"[{key}]"

    return f'["{key}"]' if not is_simple_key(key) else key


def value_to_lua(value):
    value = escape_lua_string(value)

    if value is None or value == "nil":
        formatted_value = "nil"
    elif isinstance(value, bool):
        formatted_value = str(value).lower()
    elif isinstance(value, str) and value not in ["Z_DECALS", "Z_OBJECTS"]:
        formatted_value = f'"{value}"'
    else:
        formatted_value = str(value)

    return formatted_value


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
