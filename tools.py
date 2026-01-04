import traceback, subprocess, time, config
from pathlib import Path
import Tools.generate_waves as generate_waves
import Tools.process_images as process_images
import Tools.merge_images as merge_images
import Tools.sort_table as sort_table
import Tools.split_atlas as split_atlas
import Tools.generate_atlas as generate_atlas
import Tools.measure_anchor as measure_anchor
import Tools.plist_level_to_lua as plist_level_to_lua
import Tools.plist_animation_to_lua as plist_animation_to_lua

input_path = config.input_path
output_path = config.output_path

def get_tools_data():
    return {
        "generate_waves": {
            "name": "生成波次",
            "module": generate_waves,
            "has_gui": True,
        },
        "process_images": {
            "name": "处理图像",
            "module": process_images,
            "has_gui": True,
        },
        "merge_images": {
            "name": "合并图像",
            "module": merge_images,
            "has_gui": False,
        },
        "sort_table": {
            "name": "排序表",
            "module": sort_table,
            "has_gui": False,
        },
        "split_atlas": {
            "name": "拆分图集",
            "module": split_atlas,
            "has_gui": False,
        },
        "generate_atlas": {
            "name": "合并图集",
            "module": generate_atlas,
            "has_gui": False,
        },
        "measure_anchor": {
            "name": "测量锚点",
            "module": measure_anchor,
            "has_gui": True,
        },
        "plist_level_to_lua": {
            "name": "四代关卡数据转五代",
            "module": plist_level_to_lua,
            "has_gui": False,
        },
        "plist_animation_to_lua": {
            "name": "四代动画数据转五代",
            "module": plist_animation_to_lua,
            "has_gui": False,
        },
    }
