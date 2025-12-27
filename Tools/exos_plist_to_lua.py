import math, config, plistlib, re, traceback
from typing import Dict, List, Any, Union, Tuple
from utils import is_simple_key
from pathlib import Path


def get_plist_exos_data(plist_data):
    data = {
        "fps": 30,
        "partScaleCompensation": plist_data["partScaleCompensation"],
        "animations": [],
        "parts": {},
    }

    for anim_data in plist_data["animations"]:
        a = {"name": anim_data["name"], "frames": []}

        for af in anim_data["frames"]:
            f = {
                "attachPoints": af["attachPoints"],
                "duration": af["duration"],
                "events": af["events"],
                "parts": [],
            }

            for part in af["parts"]:
                p = {
                    "name": part["name"],
                    "xform": matrix_to_transform_params(part["matrix"]),
                }

                f["parts"].append(p)

            a["frames"].append(f)

        data["animations"].append(a)

    for part in plist_data["parts"]:
        name = part["name"]
        data["parts"][name] = {
            "name": name,
            "offsetX": part["offsetX"],
            "offsetY": part["offsetY"],
        }

    return data


def matrix_to_transform_params(matrix: List[float]) -> Dict[str, float]:
    """
    将仿射变换矩阵转换为变换参数
    [a, b, c, d, tx, ty] -> {x, y, sx, sy, r, kx, ky}
    """
    a, b, c, d, tx, ty = matrix

    # 计算缩放
    sx = math.sqrt(a * a + c * c)
    sy = math.sqrt(b * b + d * d)

    # 计算旋转角度（弧度）
    r = math.atan2(c, a)

    # 计算倾斜（如果存在）
    if r:
        kx = math.atan2(-b, d) - r
        ky = math.atan2(c, a) - r
    else:
        kx = math.atan2(-b, d)
        ky = math.atan2(c, a)

    return {"x": tx, "y": ty, "sx": sx, "sy": sy, "r": r, "kx": kx, "ky": ky}


def write_exos_data(data: Dict[str, Any], filename: str):
    """
    保存为Lua格式文件
    """
    content = [
        "return {",
    ]

    def a(str):
        content.append(str)

    a(f'\tfps = {data["fps"]},')
    a(f'\tpartScaleCompensation = {data["partScaleCompensation"]},')

    # 写入animations
    a("\tanimations = {")
    for i, anim in enumerate(data["animations"]):
        a("\t\t{")
        a(f'\t\t\tname = "{anim["name"]}",')
        a("\t\t\tframes = {")

        for j, af in enumerate(anim["frames"]):
            a("\t\t\t\t{")
            a("\t\t\t\t\tparts = {")
            for ii, p in enumerate(af["parts"]):
                a("\t\t\t\t\t\t{")
                a(f'\t\t\t\t\t\t\tname = "{p["name"]}"')
                a("\t\t\t\t\t\t\txform = {")

                xform = p["xform"]
                a(f"\t\t\t\t\t\t\t\tsx = {xform["sx"]},")
                a(f"\t\t\t\t\t\t\t\tsy = {xform["sy"]},")
                a(f"\t\t\t\t\t\t\t\tkx = {xform["kx"]},")
                a(f"\t\t\t\t\t\t\t\tky = {xform["ky"]},")
                a(f"\t\t\t\t\t\t\t\tr = {xform["r"]},")
                a(f"\t\t\t\t\t\t\t\tx = {xform["x"]},")
                a(f"\t\t\t\t\t\t\t\ty = {xform["y"]}")
                a("\t\t\t\t\t\t\t}")

                if ii < len(af["parts"]) - 1:
                    a("\t\t\t\t\t\t},")
                else:
                    a("\t\t\t\t\t\t}")

            a("\t\t\t\t\t}")

            if j < len(anim["frames"]) - 1:
                a("\t\t\t\t},")
            else:
                a("\t\t\t\t}")

        a("\t\t\t}")
        if i < len(data["animations"]) - 1:
            a("\t\t},")
        else:
            a("\t\t}")

    a("\t},")
    a("\tparts = {")

    # 写入parts
    i = 0
    for name, part in data["parts"].items():
        if is_simple_key(name):
            a(f"\t\t{name} = {{")
        else:
            a(f'\t\t["{name}"] = {{')

        a(f'\t\t\tname = "{part["name"]}",')
        a(f"\t\t\toffsetX = {part["offsetX"]},")
        a(f"\t\t\toffsetY = {part["offsetY"]}")
        if i < len(data["parts"]) - 1:
            a("\t\t},")
        else:
            a("\t\t}")
        i += 1

    a("\t}")
    a("}")

    lua_content = "\n".join(content)
    file = f"{filename}.lua"

    print(f"写入骨骼动画数据{file}...")

    with open(config.output_path / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def get_input_files():
    files = []

    for file in config.input_path.iterdir():
        match = re.search(r"animations", file.stem)
        if match:
            with open(file, "rb") as f:
                plist_data = plistlib.load(f)

                match_animations = match.group()

                print(f"📖 读取文件: {file.name}")
                if match_animations:
                    file_data = (file.stem, match_animations, plist_data)

                    files.append(file_data)

    return files


def main():
    files = get_input_files()

    try:
        for name, match_animations, plist_data in files:
            data = get_plist_exos_data(plist_data)
            write_exos_data(data, name)

        print("所有文件转化完毕")
    except Exception as e:
        traceback.print_exc()


if __name__ == "__main__":
    main()
