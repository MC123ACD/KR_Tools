import json
from pathlib import Path
from lupa.luajit20 import LuaRuntime

input_path = Path("input")
output_path = Path("output")

input_path.mkdir(exist_ok=True)
output_path.mkdir(exist_ok=True)

setting_file = Path("setting.json")
lupa = LuaRuntime(unpack_returned_tuples=True)
setting = {}

log_level = "INFO"
log_file = None

with open(setting_file, "r", encoding="utf-8") as f:
    data = json.load(f)

    setting = data
