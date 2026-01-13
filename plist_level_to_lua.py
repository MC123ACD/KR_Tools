import re, traceback, config, math, plistlib
from utils import is_simple_key
import log

log = log.setup_logging(config.log_level, config.log_file)


class CconvertPlistToLua:
    def __init__(self):
        self.main_datas = {}

    def get_num_level_mode(self):
        num_mode = None

        if self.level_mode == "campaign":
            num_mode = 1
        if self.level_mode == "heroic":
            num_mode = 2
        if self.level_mode == "iron":
            num_mode = 3

        return num_mode

    def get_lua_data(self):
        if not self.main_datas.get(self.level_num):
            self.main_datas[self.level_num] = {
                "level_data": {},
                "waves_data": [None] * 3,
                "spawners_data": [None] * 3,
            }

        if self.level_mode == "data":
            self.extract_level_data()
        elif self.level_mode:
            self.extract_waves_data()

    def extract_level_data(self):
        main_data = self.main_datas[self.level_num]

        main_data["level_data"] = self.get_level_data()

    def get_level_data(self):
        data = {"name": f"level{setting["level_name_prefix"]}{self.level_num}_data.lua"}

        terrain_type = int(
            f"{setting["level_name_prefix"]}{str(self.plist_data["terrain"]).zfill(setting["level_name_leading_zero"])}"
        )

        data["hero_positions"] = self.get_hero_position()
        data["terrain_type"] = terrain_type
        data["entities_list"] = self.get_level_data_entities(terrain_type)
        data["paths"] = self.get_level_paths(data)
        data["grids"] = self.get_level_grids()
        data["nav_mesh"] = self.get_level_nav_mesh(data["entities_list"])

        return data

    def get_hero_position(self):
        hero_position = self.plist_data["hero_position"]

        if setting["is_kr5"]:
            hero_position = [
                self.plist_data["hero_position"],
                self.plist_data["hero_position"],
            ]

        return hero_position

    def get_level_data_entities(self, terrain_type):
        plist_data = self.plist_data

        entities_list = [
            {
                "template": "decal_background",
                "render.sprites[1].z": 1000,
                "render.sprites[1].name": f"Stage_{setting["level_name_prefix"]}{self.level_num}",
                "pos": {"x": 512, "y": 384},
            }
        ]

        for i, tower in enumerate(plist_data["towers"], 1):
            holder_entity = self.get_obj_holder(i, tower, terrain_type)
            entities_list.append(holder_entity)

        if "waveFlags_pc" in plist_data:
            for idx, flag in enumerate(plist_data["waveFlags_pc"], 1):
                entity = self.get_wave_flag(idx, flag)
                entities_list.append(entity)

        if "objects" in plist_data:
            for obj in plist_data["objects"]:
                obj_type = obj.get("key", obj.get("type"))

                if obj_type == "fx_repeat_forever":
                    repeat_forever_entity = self.get_obj_repeat_forever_entity(obj)
                    entities_list.append(repeat_forever_entity)
                else:
                    entities = self.get_common_obj_entities(obj, obj_type)
                    entities_list += entities

        return entities_list

    def get_obj_holder(self, i, tower, terrain_type):
        tower_type = tower["type"]
        position = tower["position"]
        if "y" in position:
            position["y"] -= 13

        holder_entity = {
            "template": "tower_holder" if tower_type == "holder" else tower_type,
            "tower.terrain_style": terrain_type,
            "pos": position,
            "tower.default_rally_pos": tower["rally_point"],
            "ui.nav_mesh_id": str(i),
            "tower.holder_id": str(i),
        }

        return holder_entity

    def get_level_paths(self, level_data):
        entities_list = level_data["entities_list"]
        level_data["invalid_path_ranges"] = []
        invalid_path_ranges = level_data["invalid_path_ranges"]

        data = {
            "connections": [],
            "paths": [],
            "curves": [],
            "active_paths": [],
        }

        # 遍历所有路径组
        for path_idx, path_group in enumerate(self.plist_data["paths_pc"]):
            # 处理paths表（原始路径数据）
            path_nodes = self.get_origin_paths(path_group)

            if path_nodes:
                data["paths"].append(path_nodes)
                data["active_paths"].append(True)

            # 处理curves（采样数据）
            first_subpath = path_group["subpaths"][0]

            curves = self.get_level_path_curves(first_subpath)
            data["curves"].append(curves)

            # 检查是否有change_node信息
            for segment in path_group["metadata"].get("segments", []):
                for modifier in segment.get("modifier", []):
                    if modifier.get("key") != "change_node":
                        continue

                    entity = self.get_change_node_entity(path_idx + 1, modifier)
                    entities_list.append(entity)

                    # 创建invalid_path_ranges条目
                    invalid_range = self.get_invalid_path_ranges(path_idx + 1, modifier)
                    invalid_path_ranges.append(invalid_range)

        return data

    def get_origin_paths(self, path_group):
        path_nodes = []

        for subpath in path_group["subpaths"]:
            points = [{"x": float(p["x"]), "y": float(p["y"])} for p in subpath]
            path_nodes.append(points)

        return path_nodes

    def get_level_path_curves(self, first_subpath):
        # 采样逻辑：首点 + 每隔8点 + 末点
        sampled_nodes = []
        sample_interval = 8
        total_points = len(first_subpath)

        # 添加首点
        sampled_nodes.append(
            {"x": float(first_subpath[0]["x"]), "y": float(first_subpath[0]["y"])}
        )

        # 每隔8个点采样
        for i in range(sample_interval, total_points, sample_interval):
            sampled_nodes.append(
                {
                    "x": float(first_subpath[i]["x"]),
                    "y": float(first_subpath[i]["y"]),
                }
            )

        # 添加末点（如果未被采样）
        if (total_points - 1) % sample_interval != 0:
            last_point = {
                "x": float(first_subpath[-1]["x"]),
                "y": float(first_subpath[-1]["y"]),
            }
            if not sampled_nodes or sampled_nodes[-1] != last_point:
                sampled_nodes.append(last_point)

        # 计算widths长度
        widths_length = (len(sampled_nodes) - 1) // 3 + 1
        widths = [40] * widths_length

        return {"nodes": sampled_nodes, "widths": widths}

    def get_change_node_entity(self, path_idx, modifier):
        return {
            "template": "controller_teleport_enemies",
            "path": path_idx,
            "start_ni": int(modifier["from"]) + 1,
            "end_ni": int(modifier["to"]) + 1,
            "duration": float(modifier["duration"]),
        }

    def get_invalid_path_ranges(self, path_idx, modifier):
        return {
            "from": int(modifier["from"]) + 1,
            "to": int(modifier["to"]) + 1,
            "path_id": path_idx,
        }

    def get_level_grids(self):
        columns = self.get_grid_columns()

        max_column = 0
        max_row = 0
        for cell in self.plist_data["grid_pc"]:
            column = int(cell["column"])
            row = int(cell["row"])

            if not columns.get(column):
                columns[column] = []

            if column > max_column:
                max_column = column
            if row > max_row:
                max_row = row

            columns[column].append((row, int(cell["terrainType"])))

        grids = []
        max_rows_in_grid = (
            max(len(cells) for cells in columns.values()) if columns else 0
        )

        for column in range(max_column + 1):
            if column in columns:
                # 对该列的数据排序（按行号降序）
                cells = sorted(columns[column], key=lambda x: x[0], reverse=True)
                # 转换地形类型：2→257，其他→1
                column_data = [257 if terrain == 2 else 1 for (row, terrain) in cells]
            else:
                # 空列：生成 max_rows_in_grid 个 1
                column_data = [1] * max_rows_in_grid

            grids.append(column_data)

        return {"ox": -170.5, "oy": -48, "cell_size": 17.0625, "grid": grids}

    def get_grid_columns(self):
        columns = {}

        # 3. 计算最大列数和行数
        max_column = 0
        max_row = 0
        for cell in self.plist_data["grid_pc"]:
            column = int(cell["column"])
            row = int(cell["row"])
            if column > max_column:
                max_column = column
            if row > max_row:
                max_row = row

            if not columns.get(column):
                columns[column] = []

            terrain_type = int(cell["terrainType"])
            columns[column].append((row, terrain_type))

        return columns

    def get_level_nav_mesh(self, entities_list):
        nav_mesh = []
        tower_entities = [e for e in entities_list if "ui.nav_mesh_id" in e]

        entities_by_id = {int(e["ui.nav_mesh_id"]): e for e in tower_entities}

        for entity in tower_entities:
            entity_id = int(entity["ui.nav_mesh_id"])
            x, y = entity["pos"]["x"], entity["pos"]["y"]
            directions = {
                "right": (float("inf"), None),
                "top": (float("inf"), None),
                "left": (float("inf"), None),
                "bottom": (float("inf"), None),
            }

            for other_id, other_entity in entities_by_id.items():
                if other_id == entity_id:
                    continue

                other_x, other_y = other_entity["pos"]["x"], other_entity["pos"]["y"]
                dx, dy = other_x - x, other_y - y
                distance = math.sqrt(dx**2 + dy**2)

                if dx > 0 and abs(dy) < abs(dx) and distance < directions["right"][0]:
                    directions["right"] = (distance, other_id)
                elif dy > 0 and abs(dy) > abs(dx) and distance < directions["top"][0]:
                    directions["top"] = (distance, other_id)
                elif dx < 0 and abs(dy) < abs(dx) and distance < directions["left"][0]:
                    directions["left"] = (distance, other_id)
                elif (
                    dy < 0 and abs(dy) > abs(dx) and distance < directions["bottom"][0]
                ):
                    directions["bottom"] = (distance, other_id)

            nav_mesh.append(
                [
                    directions["right"][1] or "nil",
                    directions["top"][1] or "nil",
                    directions["left"][1] or "nil",
                    directions["bottom"][1] or "nil",
                ]
            )

        return nav_mesh

    def get_wave_flag(self, idx, flag):
        dx = flag["pointPosition"]["x"] - flag["position"]["x"]
        dy = flag["pointPosition"]["y"] - flag["position"]["y"]

        entity = {
            "template": "editor_wave_flag",
            "editor.r": math.atan2(dy, dx),
            "editor.path_id": idx,
            "editor.len": 200,
            "pos": flag["position"],
        }

        return entity

    def get_obj_repeat_forever_entity(self, obj):
        entity = {"template": "fx_repeat_forever"}

        if "position" in obj and isinstance(obj["position"], dict):
            x, y = obj["position"]["x"], obj["position"]["y"]
            entity["pos"] = {"x": x, "y": y}

        if "anchor" in obj:
            x, y = obj["anchor"]["x"], obj["anchor"]["y"]
            entity["render.sprites[1].anchor.x"] = x
            entity["render.sprites[1].anchor.y"] = y

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
                entity["render.sprites[1].z"] = "Z_DECALS"
            elif layer == "entities":
                entity["render.sprites[1].z"] = "Z_OBJECTS"

        if "y_position_adjust" in obj:
            entity["render.sprites[1].sort_y_offset"] = obj["y_position_adjust"] * -1

        if "single_frame" in obj:
            filename = obj["single_frame"].split(".")[0]
            entity["render.sprites[1].name"] = filename
            entity["render.sprites[1].animated"] = False

        if "animations" in obj:
            animations = obj["animations"]
            if "animations_file" in animations:
                sprite_name = re.sub(r"^Stage_\d+_", "", animations["animations_file"])

                entity["render.sprites[1].name"] = (
                    f"{re.sub(r"_animations\.plist$", "", sprite_name)}_run"
                )
                entity["render.sprites[1].animated"] = True

            if "max_delay" in animations:
                entity["max_delay"] = animations["max_delay"]
            if "min_delay" in animations:
                entity["min_delay"] = animations["min_delay"]
            if "random_shift" in animations:
                entity["random_shift"] = animations["random_shift"]

        return entity

    def get_common_obj_entities(self, obj, obj_type):
        entities = []

        positions = obj["position"]
        if isinstance(positions, dict):
            positions = [positions]

        layers = obj.get("layer", [])
        if isinstance(layers, str):
            layers = [layers]

        max_count = max(len(positions), len(layers)) if (positions or layers) else 1
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

            entities.append(entity)

        return entities

    def extract_waves_data(self):
        num_level_mode = self.get_num_level_mode() - 1
        main_data = self.main_datas[self.level_num]

        main_data["waves_data"][num_level_mode] = self.get_waves_data()

        if self.plist_data["custom_spawners"]["events"]:
            if not self.main_datas[self.level_num]["level_data"].get("entities_list"):
                log.error(f"请放入{f"level{self.level_num}_data.lua"}文件")
                return

            main_data["spawners_data"][num_level_mode] = self.get_spawners_data()

    def get_waves_data(self):
        data = {
            "cash": int(self.plist_data["gold"]),
            "waves": [],
            "name": f"level{setting["level_name_prefix"]}{self.level_num}_waves_{self.level_mode}.lua",
        }

        for wave in self.plist_data["waves"]:
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
                        "fixed_sub_path": (0 if spawn["fixed_sub_path"] < 0 else 1),
                        "path": (
                            3
                            if spawn["fixed_sub_path"] < 0
                            else spawn["fixed_sub_path"] + 1
                        ),
                    }

                    new_group["spawns"].append(new_spawn)
                new_wave["groups"].append(new_group)
            data["waves"].append(new_wave)

        return data

    def get_spawners_data(self):
        spawner_data_name = f"level{setting["level_name_prefix"]}{self.level_num}_spawner_{self.level_mode}.lua"

        data = {"name": spawner_data_name}

        entities = self.handle_spawners_entities(spawner_data_name)

        positions = self.get_spawners_positions()
        points = self.get_spawners_points(positions)

        data["points"] = points
        data["groups"] = self.get_spawners_groups(points, entities)
        data["waves"] = self.get_spawners_waves(points)

        return data

    def get_spawners_positions(self):
        plist_data = self.plist_data
        positions = []
        events = plist_data["custom_spawners"]["events"]

        for wave in events.values():
            for event in wave:
                config = event["config"]
                path = config["path"] + 1

                for spawn in config["spawns"]:
                    position = spawn["position"]
                    x, y = position["x"], position["y"]

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

    def get_spawners_groups(self, points, entities):
        spawner_entities = entities["spawners"]

        groups = []

        # 为每个点位生成数字组 {1}, {2}...
        for i in range(1, len(points) + 1):
            groups.append([i])

        # 只为 spawner_entities 生成命名组
        for i, entity in enumerate(spawner_entities, 1):
            groups.append({f"som{i}": [entity["spawner.name"]]})

        return groups

    def get_spawners_waves(self, points):
        events = self.plist_data["custom_spawners"]["events"]
        waves = {}

        # 确定wave表索引
        wave_index = self.get_num_level_mode() - 1

        wave_table = {}

        for wave_name, wave_events in events.items():
            # 提取wave编号
            wave_num = re.search(r"\d+$", wave_name).group()

            wave_entries = []

            for event in wave_events:
                delay = event["delay"]
                obj = event.get("object")

                config = event["config"]
                spawns = config["spawns"]
                path = config["path"] + 1
                interval_spawns = config["interval_spawns"]

                # 如果有object，先添加object表
                if obj != None:
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

                # 只有找到匹配的point时才生成spawn表
                spawn_delay = (
                    delay + setting["custom_spawners_delay"] if obj != None else delay
                )

                for i in range(len(spawns)):
                    # 找出point索引
                    point_index = None
                    spawn = spawns[i]
                    spawn_pos = spawn["position"]
                    spawn_x, spawn_y = spawn_pos["x"], spawn_pos["y"]
                    for i, point in enumerate(points, 1):
                        if (
                            point["path"] == path
                            and point["from"]["x"] == spawn_x
                            and point["from"]["y"] == spawn_y
                        ):
                            point_index = i
                            break

                    cant = spawn["cant"]
                    interval = spawn["interval"]
                    wave_entries.append(
                        [
                            spawn_delay,
                            0,
                            point_index,
                            spawn["subpath"] + 1,
                            cant,
                            False,
                            True,
                            interval,
                            interval,
                            "enemy_" + spawn["type"],
                        ]
                    )
                    duration = (cant - 1) * interval
                    if duration < 0:
                        duration = 0
                    spawn_delay += duration + interval_spawns

            wave_table[wave_num] = wave_entries

        waves[wave_index] = wave_table

        return waves

    def handle_spawners_entities(self, spawner_data_name):
        main_data = self.main_datas[self.level_num]
        level_data_entities = main_data["level_data"]["entities_list"]
        plist_data = self.plist_data

        num_level_mode = self.get_num_level_mode()

        entities = {"spawners": [], "repeat_forever": [], "else": []}

        # 第一部分：处理 custom_spawners.objects
        objects = self.plist_data["custom_spawners"].get("objects", [])
        for i, obj in enumerate(objects, 1):
            custom_spawner_entity = self.get_custom_spawners_entity(
                i, obj, num_level_mode
            )
            entities["spawners"].append(custom_spawner_entity)
            level_data_entities.append(custom_spawner_entity)

        # 第二部分：处理 events 添加的 mega_spawner
        mega_spawner = self.get_mega_spawner(spawner_data_name, num_level_mode)

        entities["else"].append(mega_spawner)
        level_data_entities.append(mega_spawner)

        # 第三部分：处理普通 objects（非 custom_spawners.objects），待处理
        objects = plist_data.get("objects", [])
        for obj in objects:
            obj_type = obj.get("key", obj.get("type", ""))

            if obj_type == "fx_repeat_forever":
                repeat_forever_entity = self.get_obj_repeat_forever_entity(obj)
                entities["repeat_forever"].append(repeat_forever_entity)
                level_data_entities.append(repeat_forever_entity)

            elif obj_type:
                common_entities = self.get_common_obj_entities(obj, obj_type)
                entities += common_entities
                entities["else"] += common_entities
                level_data_entities += common_entities

        return entities

    def get_custom_spawners_entity(self, i, obj, game_mode):
        entity = {
            "template": obj["type"],
            "pos": obj["position"],
            "spawner.name": f"object{i}",
        }

        entity["editor.game_mode"] = game_mode

        return entity

    def get_mega_spawner(self, spawner_data_name, num_level_mode):
        return {
            "template": "mega_spawner",
            "load_file": spawner_data_name.split(".")[0],
            "editor.game_mode": num_level_mode,
        }

    def write_lua_files(self):
        levels_dir = config.output_path / "levels"
        waves_dir = config.output_path / "waves"
        levels_dir.mkdir(exist_ok=True)
        waves_dir.mkdir(exist_ok=True)

        for level_num, datas in self.main_datas.items():
            self.write_level_data_file(datas["level_data"], levels_dir, level_num)
            self.write_paths_data_file(datas["level_data"], levels_dir)
            self.write_grids_data_file(datas["level_data"], levels_dir)
            self.write_waves_data_file(datas["waves_data"], waves_dir)
            self.write_spawners_data_file(datas["spawners_data"], levels_dir)

    def write_level_data_file(self, level_data, levels_dir, level_num):
        hero_positions = level_data["hero_positions"]
        terrain = level_data["terrain_type"]
        entities_list = level_data["entities_list"]
        nav_mesh = level_data["nav_mesh"]
        invalid_path_ranges = level_data["invalid_path_ranges"]

        content = [
            "return {",
            f"\tlevel_terrain_type = {terrain},",
            "\tlocked_hero = false,",
            "\tmax_upgrade_level = 5,",
            "\tcustom_start_pos = {",
            "\t\tzoom = 1.3,",
            "\t\tpos = {",
            "\t\t\tx = 512,",
            "\t\t\ty = 384",
            "\t\t}",
            "\t},",
            "\tlevel_mode_overrides = {},",
        ]

        def a(str):
            content.append(str)

        a("\tcustom_spawn_pos = {")
        for i, pos in enumerate(hero_positions):
            a("\t\t{")
            a("\t\t\tpos = {")
            a(f"\t\t\t\tx = {pos.get("x", 0)},")
            a(f"\t\t\t\ty = {pos.get("y", 0)}")
            a("\t\t\t}")
            if i < len(hero_positions) - 1:
                a("\t\t},")
            else:
                a("\t\t}")
        a("\t},")

        a("\tentities_list = {")
        for i, entity in enumerate(entities_list):
            a("\t\t{")
            j = 0
            for key, value in entity.items():
                formatted_key = f'["{key}"]' if not is_simple_key(key) else key

                if isinstance(value, dict):
                    a(f"\t\t\t{formatted_key} = {{")
                    a(f"\t\t\t\tx = {value.get("x", 0)},")
                    a(f"\t\t\t\ty = {value.get("y", 0)}")
                    if j < len(entity) - 1:
                        a("\t\t\t},")
                    else:
                        a("\t\t\t}")
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
                    if j < len(entity) - 1:
                        a(f"\t\t\t{formatted_key} = {value_str},")
                    else:
                        a(f"\t\t\t{formatted_key} = {value_str}")

                j += 1
            if i < len(entities_list) - 1:
                a("\t\t},")
            else:
                a("\t\t}")
        a("\t},")

        a("\tnav_mesh = {")
        for i, mesh in enumerate(nav_mesh):
            a("\t\t{")
            for j, v in enumerate(mesh):
                if j < len(mesh) - 1:
                    a(f"\t\t\t{v},")
                else:
                    a(f"\t\t\t{v}")

            if i < len(nav_mesh) - 1:
                a("\t\t},")
            else:
                a("\t\t}")
        a("\t},")

        if invalid_path_ranges:
            a("\tinvalid_path_ranges = {")
            for i, invalid_range in enumerate(invalid_path_ranges):
                a("\t\t{")
                a(f"\t\t\tfrom = {invalid_range["from"]},")
                a(f"\t\t\tto = {invalid_range["to"]},")
                a(f"\t\t\tpath_id = {invalid_range["path_id"]}")
                if i < len(invalid_path_ranges) - 1:
                    a("\t\t},")
                else:
                    a("\t\t}")
            a("\t},")
        else:
            a("\tinvalid_path_ranges = {},")

        a("\trequired_exoskeletons = {},")
        a("\trequired_sounds = {},")
        a("\trequired_textures = {")
        a(
            f'\t\t"go_stage{setting["level_name_prefix"]}{str(level_num).zfill(setting["level_name_leading_zero"])}"'
        )
        a("\t}")

        a("}")

        lua_content = "\n".join(content)
        file = level_data["name"]

        log.info(f"写入关卡数据{file}...")

        with open(levels_dir / file, "w", encoding="utf-8") as f:
            f.write(lua_content)

    def write_paths_data_file(self, level_data, levels_dir):
        paths_data = level_data["paths"]
        active_paths = paths_data["active_paths"]

        content = ["return {"]

        def a(str):
            content.append(str)

        a("\tactive = {")
        for i, active in enumerate(active_paths):
            if i < len(active_paths) - 1:
                a(f"\t\t{str(active).lower()},")
            else:
                a(f"\t\t{str(active).lower()}")
        a("\t},")

        a("\tconnections = {},")

        a("\tpaths = {")
        for i, path in enumerate(paths_data["paths"]):
            a("\t\t{")
            for j, subpath in enumerate(path):
                a("\t\t\t{")
                for ii, point in enumerate(subpath):
                    a("\t\t\t\t{")
                    a(f"\t\t\t\t\tx = {point["x"]},")
                    a(f"\t\t\t\t\ty = {point["y"]}")
                    if ii < len(subpath) - 1:
                        a("\t\t\t\t},")
                    else:
                        a("\t\t\t\t}")
                if j < len(path) - 1:
                    a("\t\t\t},")
                else:
                    a("\t\t\t}")

            if i < len(paths_data["paths"]) - 1:
                a("\t\t},")
            else:
                a("\t\t}")
        a("\t},")

        a("\tcurves = {")
        for i, curve in enumerate(paths_data["curves"]):
            a("\t\t{")
            a("\t\t\tnodes = {")
            for j, node in enumerate(curve["nodes"]):
                a("\t\t\t\t{")
                a(f"\t\t\t\t\tx = {node["x"]},")
                a(f"\t\t\t\t\ty = {node["y"]}")
                if j < len(curve["nodes"]) - 1:
                    a("\t\t\t\t},")
                else:
                    a("\t\t\t\t}")
            a("\t\t\t},")
            a("\t\t\twidths = {")
            for j, w in enumerate(curve["widths"]):
                if j < len(curve["widths"]) - 1:
                    a(f"\t\t\t\t{w},")
                else:
                    a(f"\t\t\t\t{w}")
            a("\t\t\t}")
            if i < len(paths_data["curves"]) - 1:
                a("\t\t},")
            else:
                a("\t\t}")
        a("\t}")
        a("}")

        lua_content = "\n".join(content)
        file = level_data["name"].replace("data", "paths")

        log.info(f"写入路径数据{file}...")

        with open(levels_dir / file, "w", encoding="utf-8") as f:
            f.write(lua_content)

    def write_grids_data_file(self, level_data, levels_dir):
        grids_data = level_data["grids"]

        content = [
            "return {",
            f"\tox = {grids_data["ox"]},",
            f"\toy = {grids_data["oy"]},",
            f"\tcell_size = {grids_data["cell_size"]},",
        ]

        def a(str):
            content.append(str)

        a("\tgrid = {")
        for i, column in enumerate(grids_data["grid"]):
            a("\t\t{")

            for j, row_d in enumerate(column):
                if j < len(column) - 1:
                    a(f"\t\t\t{row_d},")
                else:
                    a(f"\t\t\t{row_d}")

            if i < len(grids_data["grid"]) - 1:
                a("\t\t},")
            else:
                a("\t\t}")
        a("\t}")
        a("}")

        lua_content = "\n".join(content)
        file = level_data["name"].replace("data", "grid")

        log.info(f"写入网格数据{file}...")

        with open(levels_dir / file, "w", encoding="utf-8") as f:
            f.write(lua_content)

    def write_waves_data_file(self, waves_datas, waves_dir):
        for waves_data in waves_datas:
            if not waves_data:
                continue

            content = ["return {", f"\tcash = {waves_data["cash"]},", "\tgroups = {"]

            def a(str):
                content.append(str)

            for i, wave in enumerate(waves_data["waves"]):
                a("\t\t{")
                a(f"\t\t\tinterval = {wave["interval"]},")
                a("\t\t\twaves = {")

                for j, group in enumerate(wave["groups"]):
                    a("\t\t\t\t{")
                    a(f"\t\t\t\t\tdelay = {group["delay"]},")
                    a(f"\t\t\t\t\tpath_index = {group["path_index"]},")
                    a("\t\t\t\t\tspawns = {")

                    for ii, spawn in enumerate(group["spawns"]):
                        a("\t\t\t\t\t\t{")
                        a(f"\t\t\t\t\t\t\tinterval = {spawn["interval"]},")
                        a(f'\t\t\t\t\t\t\tcreep = "{spawn["creep"]}",')
                        a(f"\t\t\t\t\t\t\tmax = {spawn["max"]},")
                        a(f"\t\t\t\t\t\t\tmax_same = {spawn["max_same"]},")
                        a(f"\t\t\t\t\t\t\tfixed_sub_path = {spawn["fixed_sub_path"]},")
                        a(f"\t\t\t\t\t\t\tpath = {spawn["path"]},")
                        a(f"\t\t\t\t\t\t\tinterval_next = {spawn["interval_next"]}")

                        if ii < len(group["spawns"]) - 1:
                            a("\t\t\t\t\t\t},")
                        else:
                            a("\t\t\t\t\t\t}")
                    a("\t\t\t\t\t}")

                    if j < len(wave["groups"]) - 1:
                        a("\t\t\t\t},")
                    else:
                        a("\t\t\t\t}")
                a("\t\t\t}")

                if i < len(waves_data["waves"]) - 1:
                    a("\t\t},")
                else:
                    a("\t\t}")
            a("\t}")
            a("}")

            lua_content = "\n".join(content)
            file = waves_data["name"]

            log.info(f"写入波次数据{file}...")

            with open(waves_dir / file, "w", encoding="utf-8") as f:
                f.write(lua_content)

    def write_spawners_data_file(self, spawners_datas, levels_dir):
        for spawners_data in spawners_datas:
            if not spawners_data:
                continue

            groups = spawners_data["groups"]
            points = spawners_data["points"]
            waves = spawners_data["waves"]

            content = ["return {", "\tgroups = {"]

            def a(str):
                content.append(str)

            for i, group in enumerate(groups):
                if isinstance(group, dict):
                    group_name = next(iter(group))
                    a(f"\t\t{group_name} = {{")
                    for name in group[group_name]:
                        a(f'\t\t\t"{name}",')
                else:
                    a("\t\t{")
                    key = group[0]
                    a(f"\t\t\t{key}")
                if i < len(groups) - 1:
                    a("\t\t},")
                else:
                    a("\t\t}")
            a("\t},")

            a("\tpoints = {")
            for i, point in enumerate(points):
                a("\t\t{")
                a(f"\t\t\tpath = {point["path"]},")
                a("\t\t\tfrom = {")
                a(f"\t\t\t\tx = {point["from"]["x"]},")
                a(f"\t\t\t\ty = {point["from"]["y"]}")
                a("\t\t\t},")
                a("\t\t\tto = {")
                a(f"\t\t\t\tx = {point["to"]["x"]},")
                a(f"\t\t\t\ty = {point["to"]["y"]}")
                a("\t\t\t}")
                if i < len(points) - 1:
                    a("\t\t},")
                else:
                    a("\t\t}")
            a("\t},")

            a("\twaves = {")
            i = 0
            for wave_idx, wave_data in waves.items():
                a("\t\t{")
                j = 0
                for sub_wave, entries in wave_data.items():
                    a(f"\t\t\t[{sub_wave}] = {{")
                    for ii, entry in enumerate(entries):
                        a("\t\t\t\t{")
                        for i, item in enumerate(entry):
                            if i < len(entry) - 1:
                                if item is None:
                                    a("\t\t\t\t\tnil,")
                                elif isinstance(item, bool):
                                    a(f"\t\t\t\t\t{item and "true" or "false"},")
                                elif isinstance(item, str):
                                    a(f'\t\t\t\t\t"{item}",')
                                else:
                                    a(f"\t\t\t\t\t{item},")
                            else:
                                if item is None:
                                    a("\t\t\t\t\tnil")
                                elif isinstance(item, bool):
                                    a(f"\t\t\t\t\t{item and "true" or "false"}")
                                elif isinstance(item, str):
                                    a(f'\t\t\t\t\t"{item}"')
                                else:
                                    a(f"\t\t\t\t\t{item}")

                        if ii < len(entries) - 1:
                            a("\t\t\t\t},")
                        else:
                            a("\t\t\t\t}")

                    if j < len(wave_data) - 1:
                        a("\t\t\t},")
                    else:
                        a("\t\t\t}")

                    j += 1

                if i < len(waves) - 1:
                    a("\t\t},")
                else:
                    a("\t\t}")

                i += 1
            a("\t}")
            a("}")

            lua_content = "\n".join(content)
            file = spawners_data["name"]

            log.info(f"写入特殊出怪数据{file}...")

            with open(levels_dir / file, "w", encoding="utf-8") as f:
                f.write(lua_content)

    def main(self, files):
        """主函数"""

        for file, level_num, level_mode, plist_data in files:
            self.plist_file = file
            self.stem_name = file.stem
            self.level_num = str(level_num).zfill(setting["level_name_leading_zero"])
            self.level_mode = level_mode
            self.plist_data = plist_data

            self.get_lua_data()

        for level_num, datas in self.main_datas.items():
            level_data_entities = datas["level_data"]["entities_list"]
            level_data_entities.sort(key=lambda x: x["template"])

        self.write_lua_files()


def get_input_files():
    level_data_files = []
    waves_data_files = []

    for file in config.input_path.iterdir():
        match = re.match(r"level(\d+)_(campaign|heroic|iron|data)", file.stem)
        if match:
            with open(file, "rb") as f:
                plist_data = plistlib.load(f)
                level_num, level_mode = match.group(1), match.group(2)

                log.info(f"📖 读取文件: {file.name}")
                if level_mode == "data":
                    file_data = (file, level_num, level_mode, plist_data)

                    level_data_files.append(file_data)

                elif level_mode:
                    file_data = (file, level_num, level_mode, plist_data)

                    waves_data_files.append(file_data)

    files = level_data_files + waves_data_files

    return files


def main():
    global setting
    setting = config.setting["plist_level_to_lua"]

    files = get_input_files()

    try:
        app = CconvertPlistToLua()
        app.main(files)

        log.info("所有文件转化完毕")
    except Exception as e:
        traceback.print_exc()


if __name__ == "__main__":
    # 执行主函数并返回退出码
    success = main()
    exit(0 if success else 1)
