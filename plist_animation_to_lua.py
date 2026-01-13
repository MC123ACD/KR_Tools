import re, traceback, config, plistlib, math
from utils import is_simple_key
import log

log = log.setup_logging(config.log_level, config.log_file)


def matrix_to_transform_params(matrix):
    """
    将仿射变换矩阵转换为变换参数
    假设变换顺序为：缩放(sx,sy) → 倾斜(k) → 旋转(r) → 平移(tx,ty)
    矩阵形式: [a, b, tx; c, d, ty]

    返回: {"x": tx, "y": ty, "sx": sx, "sy": sy, "r": r, "kx": kx, "ky": ky}
    """
    a, b, c, d, tx, ty = matrix

    # 计算平移
    x, y = tx, ty

    # 计算行列式（用于检查是否有反射）
    det = a * d - b * c

    # 处理奇异矩阵
    if abs(det) < 1e-10:
        # 接近奇异矩阵时使用近似值
        if abs(a) < 1e-10 and abs(d) < 1e-10:
            sx = math.hypot(b, c)
            sy = 0
            r = 0
            kx = 0
            ky = math.atan2(c, b) if b != 0 else 0
        else:
            sx = math.hypot(a, c)
            sy = math.hypot(b, d)
            r = math.atan2(c, a) if a != 0 else 0
            kx = math.atan2(b, d) if d != 0 else 0
            ky = 0
    else:
        # 去除旋转影响以提取缩放和倾斜
        # 计算旋转角度（atan2返回的是 -π 到 π 之间的值）
        r = math.atan2(b - c, a + d) / 2

        # 计算去除旋转后的矩阵
        cos_r = math.cos(r)
        sin_r = math.sin(r)

        # 构建旋转矩阵的逆
        # 计算 M_rot_inv = [cos(r), sin(r); -sin(r), cos(r)]
        # 然后计算 M_no_rot = M * M_rot_inv
        a_prime = a * cos_r + c * sin_r
        b_prime = b * cos_r + d * sin_r
        c_prime = -a * sin_r + c * cos_r
        d_prime = -b * sin_r + d * cos_r

        # 提取缩放和倾斜
        sx = math.copysign(math.hypot(a_prime, c_prime), det)
        sy = math.copysign(math.hypot(b_prime, d_prime), det)

        # 计算倾斜角度（通常倾斜是相同的，但这里保持kx,ky分离以匹配你的需求）
        # 注意：通常倾斜矩阵是上三角或下三角形式
        if abs(sx) > 1e-10:
            kx = math.atan2(b_prime, sx)
        else:
            kx = 0

        if abs(sy) > 1e-10:
            ky = math.atan2(c_prime, sy)
        else:
            ky = 0

    return {
        "x": x,  # 平移X
        "y": y,  # 平移Y
        "sx": sx,  # 缩放X
        "sy": sy,  # 缩放Y
        "r": r,  # 旋转角度（弧度）
        "kx": kx,  # X方向倾斜角度
        "ky": ky,  # Y方向倾斜角度
    }


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
                    f["parts"].append(
                        {
                            "alpha": p.get("alpha"),
                            "name": p["name"],
                            "xform": matrix_to_transform_params(p["matrix"]),
                        }
                    )

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

    log.info(f"写入动画数据{file}...")

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

    log.info(f"写入骨骼动画数据{file}...")

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
                    log.info(f"📖 读取文件: {file.name}")
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

        log.info("所有文件转化完毕")
    except Exception as e:
        traceback.print_exc()


if __name__ == "__main__":
    # 执行主函数并返回退出码
    success = main()
    exit(0 if success else 1)
