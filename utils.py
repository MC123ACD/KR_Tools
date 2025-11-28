import traceback, subprocess
from pathlib import Path
import Tools.generate_waves as generate_waves
import Tools.handle_images as handle_images
import Tools.luajit_decompiler as luajit_decompiler
import Tools.sort_table as sort_table
import Tools.split_atlas as split_atlas
import Tools.generate_atlas as generate_atlas
import config

input_path = config.input_path
output_path = config.output_path

def get_tools_data():
    return {
        "generate_waves": {
            "name": "生成波次",
            "module": generate_waves,
            "has_setting": True,
            "has_gui": True,
        },
        "handle_images": {
            "name": "处理图像",
            "module": handle_images,
            "has_setting": True,
            "has_gui": False,
        },
        "luajit_decompiler": {
            "name": "反编译",
            "module": luajit_decompiler,
            "has_setting": False,
            "has_gui": True,
        },
        "sort_table": {
            "name": "排序表",
            "module": sort_table,
            "has_setting": False,
            "has_gui": False,
        },
        "split_atlas": {
            "name": "拆分图集",
            "module": split_atlas,
            "has_setting": False,
            "has_gui": False,
        },
        "generate_atlas": {
            "name": "合并图集",
            "module": generate_atlas,
            "has_setting": True,
            "has_gui": False,
        },
    }


def open_output_dir():
    subprocess.run(["explorer", str(output_path)])


def run_decompiler(file_path, output_path="output"):
    """反编译lua文件"""
    subprocess.run(
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


def is_simple_key(key: str):
    """检查键名是否为简单标识符（只包含字母、数字、下划线，不以数字开头）"""
    if not key or key[0].isdigit():
        return False
    return all(c.isalnum() or c == "_" for c in key)
