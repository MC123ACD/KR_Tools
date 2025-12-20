import traceback, subprocess, time, config
from pathlib import Path
import Tools.generate_waves as generate_waves
import Tools.handle_images as handle_images
import Tools.merge_images as merge_images
import Tools.luajit_decompiler as luajit_decompiler
import Tools.sort_table as sort_table
import Tools.split_atlas as split_atlas
import Tools.generate_atlas as generate_atlas
import Tools.plist_level_to_lua as plist_level_to_lua
import Tools.plist_animation_to_lua as plist_animation_to_lua
import Tools.measure_offset_and_anchor as measure_offset_and_anchor

input_path = config.input_path
output_path = config.output_path

def clamp(value, min_value, max_value):
    """将值限制在[min_value, max_value]范围内"""
    return max(min_value, min(value, max_value))

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
        "merge_images": {
            "name": "合并图像",
            "module": merge_images,
            "has_setting": False,
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
            "has_setting": True,
            "has_gui": False,
        },
        "generate_atlas": {
            "name": "合并图集",
            "module": generate_atlas,
            "has_setting": True,
            "has_gui": False,
        },
        "plist_level_to_lua": {
            "name": "四代关卡数据转五代",
            "module": plist_level_to_lua,
            "has_setting": True,
            "has_gui": False,
        },
        "plist_animation_to_lua": {
            "name": "四代动画数据转五代",
            "module": plist_animation_to_lua,
            "has_setting": False,
            "has_gui": False,
        },
        "measure_offset_and_anchor": {
            "name": "测量锚点",
            "module": measure_offset_and_anchor,
            "has_setting": False,
            "has_gui": True,
        },
    }


def open_output_dir():
    if config.setting["main"]["open_output_dir"]:
        time.sleep(2)
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
