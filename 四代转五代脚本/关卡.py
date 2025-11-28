import plistlib, re, traceback, config
from pathlib import Path
import utils as U

input_path, output_path, setting = (
    config.input_path,
    config.output_path,
    config.setting[""],
)

class CconvertPlistToLua:
    def __init__(self):
        self.main_datas = {}

    def get_entities(self):
        stem_name = self.plist_file.stem
        plist_data = self.plist_data
        game_mode = None
        if "_campaign" in stem_name:
            game_mode = 1
        elif "_heroic" in stem_name:
            game_mode = 2
        elif "_iron" in stem_name:
            game_mode = 3

        entities = {"spawners": [], "repeat_forever": [], "else": []}

        # 第一部分：处理 custom_spawners.objects
        objects = plist_data.get("custom_spawners", {}).get("objects", [])

        # 添加spawner对象（custom_spawners.objects）
        for i, obj in enumerate(objects, 1):
            entity = {
                "template": obj["type"],
                "pos": obj["position"],
                "spawner.name": f"object{i}",
            }

            if game_mode:
                entity["editor.game_mode"] = game_mode

            entities["spawners"].append(entity)

        # 第二部分：处理 events 添加的 mega_spawner
        events = plist_data.get("custom_spawners", {}).get("events", {})

        if events:
            mega_spawner = {"template": "mega_spawner", "load_file": stem_name}

            entities["else"].append(mega_spawner)

        # 第三部分：处理普通 objects（非 custom_spawners.objects），待处理
        objects = plist_data.get("objects", [])
        for obj in objects:
            obj_type = obj.get("key", obj.get("type", ""))

            if obj_type == "fx_repeat_forever":
                lua_entity = {"template": "fx_repeat_forever"}

                if "position" in obj and isinstance(obj["position"], dict):
                    x, y = obj["position"]["x"], obj["position"]["y"]
                    lua_entity["pos"] = {"x": x, "y": y}

                if "anchor" in obj:
                    x, y = obj["anchor"]["x"], obj["anchor"]["y"]
                    lua_entity["render.sprites[1].anchor.x"] = x
                    lua_entity["render.sprites[1].anchor.y"] = y

                if "scale" in obj:
                    scale = obj["scale"]
                    if "x" in scale:
                        x, y = scale["x"], scale["y"]
                        entity["render.sprites[1].scale.x"] = x
                        entity["render.sprites[1].scale.y"] = y
                    else:
                        entity["render.sprites[1].scale.x"] = scale
                        entity["render.sprites[1].scale.y"] = scale

                if "layer" in obj:
                    layer = obj["layer"]
                    if layer == "decals":
                        lua_entity["render.sprites[1].z"] = "Z_DECALS"
                    elif layer == "entities":
                        lua_entity["render.sprites[1].z"] = "Z_OBJECTS"

                if "y_position_adjust" in obj:
                    lua_entity["render.sprites[1].sort_y_offset"] = (
                        obj["y_position_adjust"] * -1
                    )

                if "single_frame" in obj:
                    filename = obj["single_frame"].split(".")[0]
                    lua_entity["render.sprites[1].name"] = filename
                    lua_entity["render.sprites[1].animated"] = False

                if "animations" in obj:
                    animations = obj["animations"]
                    if "animations_file" in animations:
                        anim_file = animations["animations_file"]

                        lua_entity["render.sprites[1].name"] = (
                            f"{re.sub(r"_animations\.plist$", "", anim_file)}_run"
                        )
                        lua_entity["render.sprites[1].animated"] = True

                    if "max_delay" in animations:
                        lua_entity["max_delay"] = animations["max_delay"]
                    if "min_delay" in animations:
                        lua_entity["min_delay"] = animations["min_delay"]
                    if "random_shift" in animations:
                        lua_entity["random_shift"] = animations["random_shift"]

                entities["repeat_forever"].append(lua_entity)

            elif obj_type:
                positions = obj.get("position", [])
                if isinstance(positions, dict):
                    positions = [positions]

                layers = obj.get("layer", [])
                if isinstance(layers, str):
                    layers = [layers]

                max_count = (
                    max(len(positions), len(layers)) if (positions or layers) else 1
                )
                for i in range(max_count):
                    if obj_type == "defense_point":
                        entity = {
                            "template": "decal_defend_point5",
                            "editor.flip": 0,
                            "editor.exit_id": 1,
                            "editor.alpha": 10,
                            "editor.orientation": 1,
                        }
                        if i < len(positions):
                            entity["pos"] = positions[i]

                        entities["else"].append(entity)
                    else:
                        entity = {
                            "template": (
                                "decal_defense_flag5"
                                if obj_type == "defense_flag"
                                else obj_type
                            )
                        }

                        if i < len(positions):
                            entity["pos"] = positions[i]

                        if i < len(layers):
                            z = "Z_DECALS" if layers[i] == "decals" else "Z_OBJECTS"
                            entity["render.sprites[1].z"] = z

                        if obj_type == "defense_flag":
                            entity["editor.flip"] = 0
                            entity["editor.tag"] = 0

                        entities["else"].append(entity)

        return entities

    def get_spawners_positions(self):
        plist_data = self.plist_data
        positions = []
        events = plist_data.get("custom_spawners", {}).get("events", {})

        for wave in events.values():
            for event in wave:
                config = event.get("config", {})
                path = config.get("path", -1) + 1  # 路径索引从1开始

                for spawn in config["spawns"]:
                    position = spawn.get("position", {})
                    x, y = position.get("x", 0), position.get("y", 0)

                    if x and y and path:
                        positions.append({"path": path, "x": x, "y": y})

        return positions

    def get_spawners_points(self, positions):
        seen = set()
        unique_positions = []

        for pos in positions:
            key = (pos["x"], pos["y"], pos["path"])
            if key not in seen:
                seen.add(key)
                unique_positions.append(pos)

        points = []

        for pos in unique_positions:
            points.append(
                {
                    "path": pos["path"],
                    "from": {"x": pos["x"], "y": pos["y"]},
                    "to": {"x": pos["x"], "y": pos["y"]},
                }
            )

        return points

    def get_spawners_groups(self, points):
        try:
            spawner_entities = self.main_datas[self.stem_name]["level_data"]["entities"][
                "spawners"
            ]
        except KeyError as e:
            print("")

        groups = []

        # 为每个路径点生成数字组 {1}, {2}...
        for i in range(1, len(points) + 1):
            groups.append({i})

        # 只为 spawner_entities 生成命名组
        for i, entity in enumerate(spawner_entities, 1):
            groups.append({f"som{i}": [entity["spawner.name"]]})

        return groups

    def get_spawners_waves(self, plist_path, points):
        with open(plist_path, "rb") as f:
            plist_data = plistlib.load(f)

        events = plist_data.get("custom_spawners", {}).get("events", {})
        waves = {}

        # 确定wave表索引
        stem_name = self.plist_file.stem
        wave_index = 1  # 默认
        if "_heroic" in stem_name:
            wave_index = 2
        elif "_iron" in stem_name:
            wave_index = 3

        wave_table = {}

        for wave_name, wave_events in events.items():
            # 提取wave编号
            wave_num = int(re.search(r"wave(\d+)", wave_name).group(1))

            wave_entries = []

            for event in wave_events:
                delay = event.get("delay", 0)
                obj = event.get("object", None)
                config = event.get("config", {})
                spawns = config.get("spawns", [])
                path = config.get("path", -1) + 1
                interval_spawns = config.get("interval_spawns", 0)

                # 如果有object，先添加object表
                if obj is not None:
                    wave_entries.append(
                        [
                            delay,
                            0,
                            f"som{obj+1}",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "CUSTOM",
                            True,
                        ]
                    )

                # 添加spawn表
                if spawns:
                    # 只有找到匹配的point时才生成spawn表
                    if obj is not None:
                        spawn_delay = delay + 1.6
                    else:
                        spawn_delay = delay

                    for i in range(len(spawns)):
                        # 找出point索引
                        point_index = None
                        spawn = spawns[i]
                        spawn_pos = spawn.get("position", {})
                        spawn_x, spawn_y = spawn_pos.get("x", 0), spawn_pos.get("y", 0)
                        for i, point in enumerate(points, 1):
                            if (
                                point["path"] == path
                                and point["from"]["x"] == spawn_x
                                and point["from"]["y"] == spawn_y
                            ):
                                point_index = i
                                break

                        if point_index is not None:
                            cant = spawn.get("cant", 0)
                            interval = spawn.get("interval", 0)
                            wave_entries.append(
                                [
                                    spawn_delay,
                                    0,
                                    point_index,
                                    spawn.get("subpath", -1) + 1,
                                    cant,
                                    False,
                                    True,
                                    interval,
                                    interval,
                                    "enemy_" + spawn.get("type", ""),
                                ]
                            )
                            duration = (cant - 1) * interval
                            if duration < 0:
                                duration = 0
                            spawn_delay += duration + interval_spawns

            if wave_entries:
                wave_table[wave_num] = wave_entries

        if wave_table:
            waves[wave_index] = wave_table
        return waves

    def convert_waves_plist_to_lua(self, plist_path):
        """处理第二种类型的plist文件（包含waves数据）"""
        stem_name = self.plist_file.stem

        parts = stem_name.split("_")

        if len(parts) < 2:
            print(f"跳过文件 {stem_name}：文件名格式不符合要求，应为levelXX_YYY.plist")
            return None

        level_num = parts[0][5:]  # 从levelXX中提取XX
        mode_name = parts[1]  # 提取YYY

        # 生成lua文件内容
        lua_content = "return {\n"
        lua_content += f"\tcash = {lua_data['cash']},\n"
        lua_content += "\tgroups = {\n"

        for group in lua_data["groups"]:
            lua_content += "\t\t{\n"
            lua_content += f"\t\t\tinterval = {group['interval']},\n"
            lua_content += "\t\t\twaves = {\n"

            for wave in group["waves"]:
                lua_content += "\t\t\t\t{\n"
                lua_content += f"\t\t\t\t\tdelay = {wave['delay']},\n"
                lua_content += f"\t\t\t\t\tpath_index = {wave['path_index']},\n"
                lua_content += "\t\t\t\t\tspawns = {\n"

                for spawn in wave["spawns"]:
                    lua_content += "\t\t\t\t\t\t{\n"
                    lua_content += f"\t\t\t\t\t\t\tinterval = {spawn['interval']},\n"
                    lua_content += f"\t\t\t\t\t\t\tmax_same = {spawn['max_same']},\n"
                    lua_content += (
                        f"\t\t\t\t\t\t\tfixed_sub_path = {spawn['fixed_sub_path']},\n"
                    )
                    lua_content += f"\t\t\t\t\t\t\tcreep = \"{spawn['creep']}\",\n"
                    lua_content += f"\t\t\t\t\t\t\tpath = {spawn['path']},\n"
                    lua_content += (
                        f"\t\t\t\t\t\t\tinterval_next = {spawn['interval_next']},\n"
                    )
                    lua_content += f"\t\t\t\t\t\t\tmax = {spawn['max']}\n"
                    lua_content += "\t\t\t\t\t\t},\n"

                lua_content = lua_content.rstrip(",\n") + "\n"
                lua_content += "\t\t\t\t\t}\n"
                lua_content += "\t\t\t\t},\n"

            lua_content = lua_content.rstrip(",\n") + "\n"
            lua_content += "\t\t\t}\n"
            lua_content += "\t\t},\n"

        lua_content = lua_content.rstrip(",\n") + "\n"
        lua_content += "\t}\n"
        lua_content += "}"

        return lua_content, f"level4{level_num}_waves_{mode_name}.lua"

    def convert_to_lua(points, entities, groups, waves):
        lua_code = "return {\n"

        if entities:
            lua_code += "\tentities_list = {\n"
            for entity in entities:
                lua_code += "\t\t{\n"
                for key, value in entity.items():
                    # 检查key是否是有效的Lua标识符（只包含字母数字下划线且不以数字开头）
                    is_valid_identifier = re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key)
                    formatted_key = f'["{key}"]' if not is_valid_identifier else key

                    if isinstance(value, dict):
                        lua_code += f"\t\t\t{formatted_key} = {{\n"
                        lua_code += f"\t\t\t\tx = {value.get('x', 0)},\n"
                        lua_code += f"\t\t\t\ty = {value.get('y', 0)}\n"
                        lua_code += "\t\t\t},\n"
                    else:
                        value_str = (
                            "nil"
                            if value is None
                            else (
                                "true"
                                if value is True
                                else (
                                    "false"
                                    if value is False
                                    else (
                                        f'"{value}"'
                                        if isinstance(value, str)
                                        and value not in ["Z_DECALS", "Z_OBJECTS"]
                                        else str(value)
                                    )
                                )
                            )
                        )
                        lua_code += f"\t\t\t{formatted_key} = {value_str},\n"
                lua_code += "\t\t},\n"
            lua_code += "\t},\n"

        if groups:
            lua_code += "\tgroups = {\n"
            for group in groups:
                if isinstance(group, dict):
                    group_name = next(iter(group))
                    lua_code += f"\t\t{group_name} = {{\n"
                    for name in group[group_name]:
                        lua_code += f'\t\t\t"{name}",\n'
                    lua_code += "\t\t},\n"
                else:
                    lua_code += "\t\t{\n"
                    if group:
                        key = next(iter(group))
                        lua_code += f"\t\t\t{key}\n"
                    lua_code += "\t\t},\n"
            lua_code += "\t},\n"

        if points:
            lua_code += "\tpoints = {\n"
            for point in points:
                lua_code += "\t\t{\n"
                lua_code += f"\t\t\tpath = {point['path']},\n"
                lua_code += f"\t\t\tfrom = {{\n\t\t\t\tx = {point['from']['x']},\n\t\t\t\ty = {point['from']['y']}\n\t\t\t}},\n"
                lua_code += f"\t\t\tto = {{\n\t\t\t\tx = {point['to']['x']},\n\t\t\t\ty = {point['to']['y']}\n\t\t\t}}\n"
                lua_code += "\t\t},\n"
            lua_code += "\t},\n"

        if waves:
            lua_code += "\twaves = {\n"
            for wave_index, wave_data in waves.items():
                lua_code += f"\t\t[{wave_index}] = {{\n"
                for sub_wave, entries in wave_data.items():
                    lua_code += f"\t\t\t[{sub_wave}] = {{\n"
                    for entry in entries:
                        lua_code += "\t\t\t\t{\n"
                        for i, item in enumerate(entry):
                            if i == len(entry) - 1:
                                if item is None:
                                    lua_code += "\t\t\t\t\tnil\n"
                                elif isinstance(item, bool):
                                    lua_code += (
                                        f"\t\t\t\t\t{item and 'true' or 'false'}\n"
                                    )
                                elif isinstance(item, str):
                                    lua_code += f'\t\t\t\t\t"{item}"\n'
                                else:
                                    lua_code += f"\t\t\t\t\t{item}\n"
                            else:
                                if item is None:
                                    lua_code += "\t\t\t\t\tnil,\n"
                                elif isinstance(item, bool):
                                    lua_code += (
                                        f"\t\t\t\t\t{item and 'true' or 'false'},\n"
                                    )
                                elif isinstance(item, str):
                                    lua_code += f'\t\t\t\t\t"{item}",\n'
                                else:
                                    lua_code += f"\t\t\t\t\t{item},\n"
                        lua_code += "\t\t\t\t},\n"
                    lua_code += "\t\t\t},\n"
                lua_code += "\t\t},\n"
            lua_code += "\t},\n"

        lua_code += "}"
        return lua_code

    def get_waves_data(self):
        plist_data = self.plist_data

        data = {"cash": plist_data["gold"], "waves": []}

        for wave in plist_data["waves"]:
            new_wave = {"interval": wave["interval"], "groups": []}

            for group in wave["subwaves"]:
                new_group = {
                    "delay": group["interval"],
                    "path_index": group["path_index"] + 1,
                    "spawns": [],
                }

                for spawn in group["spawns"]:
                    new_spawn = {
                        "interval": spawn["interval"],
                        "creep": "enemy_" + spawn["enemy"],
                        "max": spawn["cant"],
                        "interval_next": spawn["interval_next_spawn"],
                        "max_same": 0,
                        "fixed_sub_path": spawn["fixed_sub_path"],
                    }

                    new_group["spawns"].append(new_spawn)

                new_wave["groups"].append(new_group)

            data["waves"].append(new_wave)

        return data

    def get_spawners_data(self):
        data = {}

        positions = self.get_spawners_positions()

        data["points"] = self.get_spawners_points(positions)
        data["groups"] = self.get_spawners_groups(data["points"])
        data["waves"] = self.get_spawners_waves()

        return data

    def get_level_data(self):
        data = {}

        data["entities"] = self.get_entities()

        return data

    def extract_level_data(self):
        stem_name = self.stem_name
        main_data = self.main_datas[stem_name]

        main_data["level_data"] = self.get_level_data()
        main_data["level_data"]["name"] = f"level4{self.level_num}_data.lua"

    def extract_waves_data(self):
        main_data = self.main_datas[self.stem_name]

        main_data["waves_data"] = self.get_waves_data()
        main_data["spawners_data"] = self.get_spawners_data()
        main_data["waves_data"]["name"] = f"level4{self.level_num}_waves_{self.level_mode}.lua"
        main_data["spawners_data"]["name"] = f"level4{self.level_num}_spawner.lua"

    def get_lua_data(self):
        self.main_datas[self.stem_name] = {
            "level_data": {},
            "waves_data": {},
            "spawners_data": {},
        }

        if self.level_mode == "data":
            self.extract_level_data()
        elif self.level_mode:
            self.extract_waves_data()

    def main(self, level_data_files, waves_data_files):
        """主函数"""

        for file, level_num, level_mode, plist_data in level_data_files:
            self.file = file
            self.stem_name = file.stem
            self.level_num = level_num
            self.level_mode = level_mode
            self.plist_data = plist_data

            self.get_lua_data()

        for file, level_num, level_mode, plist_data in waves_data_files:
            self.file = file
            self.stem_name = file.stem
            self.level_num = level_num
            self.level_mode = level_mode
            self.plist_data = plist_data

            self.get_lua_data()

        print("所有文件处理完成")


def get_input_files():
    level_data_files = []
    waves_data_files = []

    for file in input_path.iterdir():
        print(f"📖 读取文件: {file}")

        with open(file, "rb") as f:
            plist_data = plistlib.load(f)

        match = re.match(r"level(\d+)_(campaign|heroic|iron|data)", file.stem)
        level_num, level_mode = match.group(1), match.group(2)

        if level_mode == "data":
            file_data = (file, level_num, level_mode, plist_data)

            level_data_files.append(file_data)

        elif level_mode:
            file_data = (file, level_num, level_mode, plist_data)

            waves_data_files.append(file_data)

    return level_data_files, waves_data_files


if __name__ == "__main__":
    level_data_files, waves_data_files = get_input_files()

    try:
        app = CconvertPlistToLua()
        app.main(level_data_files, waves_data_files)
    except Exception as e:
        traceback.print_exc()

    input("程序执行完毕，按回车键退出...")
