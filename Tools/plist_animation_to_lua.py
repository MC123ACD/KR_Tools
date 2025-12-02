import re, traceback, config, math, plistlib
import utils as U

def get_common_animations_data(plist_data):
    data = {}

    animations = plist_data["animations"]

    for anim_name, anim_data in animations.items():
        data[re.sub(r"^Stage_\d+_", "", anim_name)] = {
            "prefix": anim_data["prefix"],
            "to": anim_data["toIndex"],
            "from": anim_data["fromIndex"],
        }

    return data

def get_layer_animations_data(plist_data):
    data = {}

    animations = plist_data["animations"]

    for anim_name, anim_data in animations.items():
        match = re.match(r"(.+)_(.+)", anim_name)
        prefix, action = match.group(1), match.group(2)
        new_key = f"{prefix}X_{action}"

        data[re.sub(r"^Stage_\d+_", "", new_key)] = {
            "layer_prefix": anim_data["prefix"] + "%i",
            "layer_to": anim_data["layerEnd"],
            "layer_from": anim_data["layerStart"],
            "to": anim_data["toIndex"],
            "from": anim_data["fromIndex"],
        }

    return data

def write_common_animations_data(data, name):
    content = [
        "return {",
    ]

    def a(str):
        content.append(str)

    i = 0
    for anim_name, anim_data in data.items():
        a(f"\t{anim_name} = {{")
        a(f"\t\tprefix = \"{anim_data["prefix"]}\",")
        a(f"\t\tto = {anim_data["to"]},")
        a(f"\t\tfrom = {anim_data["from"]}")
        if i < len(data) - 1:
            a("\t},")
        else:
            a("\t}")

        i += 1

    a("}")

    lua_content = "\n".join(content)
    file = f"{name}.lua"

    print(f"写入动画数据{file}...")

    with open(config.output_path / file, "w", encoding="utf-8") as f:
        f.write(lua_content)

def write_layer_animations_data(data, name):
    content = [
        "return {",
    ]

    def a(str):
        content.append(str)

    i = 0
    for anim_name, anim_data in data.items():
        a(f"\t{anim_name} = {{")
        a(f'\t\tlayer_prefix = "{anim_data["layer_prefix"]}",')
        a(f"\t\tlayer_to = {anim_data["layer_to"]},")
        a(f"\t\tlayer_from = {anim_data["layer_from"]}")
        a(f"\t\tto = {anim_data["to"]},")
        a(f"\t\tfrom = {anim_data["from"]}")
        if i < len(data) - 1:
            a("\t},")
        else:
            a("\t}")

        i += 1

    a("}")

    lua_content = "\n".join(content)
    file = f"{name}.lua"

    print(f"写入层级动画数据{file}...")

    with open(config.output_path / file, "w", encoding="utf-8") as f:
        f.write(lua_content)

def get_input_files():
    files = []

    for file in config.input_path.iterdir():
        with open(file, "rb") as f:
            plist_data = plistlib.load(f)

        match = re.search(r"layer_animations|animations", file.stem)
        if match:
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
            if match_animations == "animations":
                ani_data = get_common_animations_data(plist_data)
                write_common_animations_data(ani_data, name)
            elif match_animations == "layer_animations":
                l_ani_data = get_layer_animations_data(plist_data)
                write_layer_animations_data(l_ani_data, name)

        print("所有文件转化完毕")

        U.open_output_dir()
    except Exception as e:
        traceback.print_exc()
