import re, traceback, config, plistlib, math
from utils import is_simple_key


def matrix_to_transform_params(matrix):
    """
    将仿射变换矩阵转换为变换参数
    [a, b, c, d, tx, ty] -> {x, y, sx, sy, r, kx, ky}
    """
    a, b, c, d, tx, ty = matrix

    # 计算缩放
    sx = math.sqrt(a * a + c * c)
    sy = math.sqrt(b * b + d * d)

    # 计算旋转弧度
    r = math.atan2(c, a)

    # 计算倾斜
    kx = math.atan2(-b, d) - r
    ky = math.atan2(c, a) - r

    return {"x": tx, "y": ty, "sx": sx, "sy": sy, "r": r, "kx": kx, "ky": ky}


def get_animations_data(plist_data):
    animations = plist_data["animations"]

    if isinstance(animations, dict):
        animations_data = {}

        layer_keys = ["layerStart", "layerEnd"]

        for anim_name, anim_data in plist_data["animations"].items():
            if any(key in anim_data for key in layer_keys):
                match = re.match(r"(.+)_(.+)", anim_name)
                prefix, action = match.group(1), match.group(2)

                new_key = f"{prefix}X_{action}"

                if not re.search("layer$", "prefix"):
                    new_key = f"{prefix}_layerX_{action}"

                animations_data[re.sub(r"^Stage_\d+_", "", new_key)] = {
                    "layer_prefix": anim_data["prefix"] + "%i",
                    "layer_to": anim_data["layerEnd"],
                    "layer_from": anim_data["layerStart"],
                    "to": anim_data["toIndex"],
                    "from": anim_data["fromIndex"],
                    "is_layer": True,
                }
            else:
                animations_data[re.sub(r"^Stage_\d+_", "", anim_name)] = {
                    "prefix": anim_data["prefix"],
                    "to": anim_data["toIndex"],
                    "from": anim_data["fromIndex"],
                    "is_layer": False,
                }

        return animations_data, False
    elif isinstance(animations, list):
        exoskeletons_data = {
            "fps": 30,
            "partScaleCompensation": plist_data["partScaleCompensation"],
            "animations": [],
            "parts": {},
        }

        for anim_data in animations:
            a = {"name": anim_data["name"], "frames": []}

            for af in anim_data["frames"]:
                f = {
                    "attachPoints": af["attachPoints"],
                    "duration": af["duration"],
                    "events": af["events"],
                    "parts": [],
                }

                for p in af["parts"]:
                    f["parts"].append({
                        "alpha": p.get("alpha"),
                        "name": p["name"],
                        "xform": matrix_to_transform_params(p["matrix"]),
                    })

                a["frames"].append(f)

            exoskeletons_data["animations"].append(a)

        for part in plist_data["parts"]:
            name = part["name"]
            exoskeletons_data["parts"][name] = {
                "name": name,
                "offsetX": part["offsetX"],
                "offsetY": part["offsetY"],
            }

        return exoskeletons_data, True


def write_common_animations_data(data, filename):
    content = [
        "return {",
    ]

    def a(str):
        content.append(str)

    is_layer = False

    i = 0
    for anim_name, anim_data in data.items():
        if is_simple_key(anim_name):
            a(f"\t{anim_name} = {{")
        else:
            a(f'\t["{anim_name}"] = {{')

        if anim_data["is_layer"]:
            a(f'\t\tlayer_prefix = "{anim_data["layer_prefix"]}",')
            a(f"\t\tlayer_to = {anim_data["layer_to"]},")
            a(f"\t\tlayer_from = {anim_data["layer_from"]},")
            is_layer = True
        else:
            a(f'\t\tprefix = "{anim_data["prefix"]}",')
        a(f"\t\tto = {anim_data["to"]},")
        a(f"\t\tfrom = {anim_data["from"]}")
        if i < len(data) - 1:
            a("\t},")
        else:
            a("\t}")

        i += 1

    a("}")

    lua_content = "\n".join(content)
    file = f"{filename}.lua"

    if is_layer and not re.search(r"layer_animations", filename):
        file = file.replace("animations", "layer_animations")

    output_dir = config.output_path / "animations"
    output_dir.mkdir(exist_ok=True)

    print(f"写入动画数据{file}...")

    with open(output_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def write_exos_data(data, filename):
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
                a(f'\t\t\t\t\t\t\tname = "{p["name"]}",')
                if p["alpha"]:
                    a(f'\t\t\t\t\t\t\talpha = "{p["alpha"]}",')
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

    output_dir = config.output_path / "exoskeletons"
    output_dir.mkdir(exist_ok=True)

    print(f"写入骨骼动画数据{file}...")

    with open(output_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def get_input_files():
    files = []

    for file in config.input_path.iterdir():
        match = re.search(r"layer_animations|animations", file.stem)
        if match:
            with open(file, "rb") as f:
                plist_data = plistlib.load(f)

                if match.group():
                    print(f"📖 读取文件: {file.name}")
                    file_data = (file.stem, plist_data)

                    files.append(file_data)

    return files


def main():
    files = get_input_files()

    try:
        for name, plist_data in files:
            ani_data, is_exo = get_animations_data(plist_data)

            if is_exo:
                write_exos_data(ani_data, name)
            else:
                write_common_animations_data(ani_data, name)

        print("所有文件转化完毕")
    except Exception as e:
        traceback.print_exc()
