import re, traceback, math, plistlib
import lib.config as config
from lib.classes import WriteLua
from lib.templates import (
    write_level_data_template,
    write_waves_data_template,
    write_spawners_data_template,
    write_paths_data_template,
    write_grids_data_template,
)
import lib.log as log

# 设置日志记录
log = log.setup_logging(config.log_level, config.log_file)

# 全局存储所有关卡的主要数据，键为关卡编号，值为该关卡的所有数据
main_datas = {}


def get_lua_data(level_num, level_mode, plist_data):
    """
    根据关卡模式提取对应的Lua数据

    根据关卡模式（data/waves）调用不同的数据提取方法：
    - data模式：提取关卡基本数据（地形、实体、路径等）
    - waves模式：提取波次数据

    Args:
        level_num (str): 关卡编号
        level_mode (str): 关卡模式，可以是'data'、'campaign'、'heroic'或'iron'
        plist_data (dict): 从Plist文件解析出的数据
    """

    # 初始化当前关卡的数据结构
    if not main_datas.get(level_num):
        main_datas[level_num] = {
            "level_data": {},  # 关卡基础数据（地形、实体、导航网格等）
            "paths_data": {},  # 路径数据（连接、路径、曲线等）
            "grids_data": {},  # 网格数据（地形单元格）
            "waves_data": [None] * 3,  # 三种模式波次数据 [campaign, heroic, iron]
            "spawners_data": [None] * 3,  # 三种模式刷怪点数据
        }

    main_data = main_datas[level_num]
    # 基础文件名前缀，例如：level_001
    base_name = f"level{setting['level_name_prefix']}{level_num}"

    # 根据模式调用不同的提取方法
    if level_mode == "data":
        # 提取关卡基础数据
        main_data["level_data"] = extract_level_data(level_num, plist_data)
        main_data["level_data"]["name"] = f"{base_name}_data.lua"
        # 提取路径数据
        main_data["paths_data"] = extract_paths_data(plist_data, main_data)
        main_data["paths_data"]["name"] = f"{base_name}_paths.lua"
        # 提取网格数据
        main_data["grids_data"] = extract_grids_data(plist_data)
        main_data["grids_data"]["name"] = f"{base_name}_grid.lua"
        return

    # 确保关卡数据已存在（需要先处理data文件）
    if not main_data["level_data"].get("entities_list"):
        log.error(f"请放入level{level_num}_data.lua 文件")
        return

    # 获取关卡模式对应的数字索引
    num_level_mode = get_num_level_mode(level_mode)
    waves_data = main_data["waves_data"]
    # 提取波次数据
    waves_data[num_level_mode] = extract_waves_data(plist_data)
    waves_data[num_level_mode]["name"] = f"{base_name}_waves_{level_mode}.lua"

    # 如果有自定义刷怪点，提取刷怪点数据
    if not plist_data["custom_spawners"]["events"]:
        return
    
    spawners_data = main_data["spawners_data"]
    spawner_data_name = f"{base_name}_spawner_{level_mode}.lua"

    # 提取刷怪点数据
    spawners_data[num_level_mode] = extract_spawners_data(
        spawner_data_name, plist_data, main_data, num_level_mode
    )
    spawners_data[num_level_mode]["name"] = spawner_data_name


def extract_level_data(level_num, plist_data):
    """
    提取关卡基础数据（地形、实体、导航网格等）

    Args:
        level_num (str): 关卡编号
        plist_data (dict): 从Plist文件解析出的数据

    Returns:
        dict: 包含关卡所有基础数据的字典
    """
    data = {
        "required_textures": [
            f"go_stage{setting['level_name_prefix']}{str(level_num).zfill(setting['level_name_leading_zero'])}"
        ]
    }

    # 计算地形类型（带前缀和补零）
    terrain_type = int(
        f"{setting['level_name_prefix']}"
        f"{str(plist_data['terrain']).zfill(setting['level_name_leading_zero'])}"
    )

    # 组装关卡数据
    data["hero_positions"] = get_hero_position(plist_data["hero_position"])
    data["terrain_type"] = terrain_type
    data["entities_list"] = get_level_data_entities(level_num, terrain_type, plist_data)
    data["nav_mesh"] = get_level_nav_mesh(data["entities_list"])

    return data


def get_hero_position(hero_position):
    """
    获取英雄起始位置

    Kingdom Rush 5支持双英雄位置，4代只有一个位置
    如果是KR5模式，复制同一位置作为第二个英雄位置

    Args:
        hero_position (dict): 英雄位置数据，包含x和y坐标

    Returns:
        list: 英雄位置列表，每个位置是{x, y}字典
    """
    if not setting["is_kr5"]:
        return hero_position
    # KR5需要两个英雄位置，复制同一位置
    return (
        hero_position,
        hero_position,
    )


def get_level_data_entities(level_num, terrain_type, plist_data):
    """
    提取关卡中的所有实体对象

    Args:
        level_num (str): 关卡编号
        terrain_type (int): 地形类型编号
        plist_data (dict): 从Plist文件解析出的数据

    Returns:
        list: 实体对象列表，每个实体是一个配置字典
    """
    entities_list = []

    # 1. 添加背景装饰层实体
    entities_list.append(
        {
            "template": "decal_background",
            "render.sprites[1].z": 1000,  # 渲染层级
            "render.sprites[1].name": f"Stage_{setting['level_name_prefix']}{level_num}",
            "pos": {"x": 512, "y": 384},  # 中心位置
        }
    )

    # 2. 添加塔位实体
    for i, tower in enumerate(plist_data["towers"], 1):
        holder_entity = get_obj_holder(i, tower, terrain_type)
        entities_list.append(holder_entity)

    # 3. 添加波次旗帜实体（指示怪物路径起点）
    if "waveFlags_pc" in plist_data:
        for idx, flag in enumerate(plist_data["waveFlags_pc"], 1):
            entity = get_wave_flag(idx, flag)
            entities_list.append(entity)

    # 4. 添加其他对象实体（特效、装饰物等）
    if "objects" in plist_data:
        for obj in plist_data["objects"]:
            obj_type = obj.get("key", obj.get("type"))

            if obj_type == "fx_repeat_forever":
                # 循环特效实体
                repeat_forever_entity = get_obj_repeat_forever_entity(obj)
                entities_list.append(repeat_forever_entity)
            else:
                # 普通实体（防御点、旗帜等）
                entities = get_common_obj_entities(obj, obj_type)
                entities_list += entities

    return entities_list


def get_obj_holder(i, tower, terrain_type):
    """
    创建塔位实体

    Args:
        i (int): 塔位编号
        tower (dict): 塔位数据
        terrain_type (int): 地形类型

    Returns:
        dict: 塔位实体配置
    """
    tower_type = tower["type"]
    position = tower["position"]

    # Y坐标调整（4代和5代的坐标系差异）
    if "y" in position:
        position["y"] -= 13

    holder_entity = {
        "template": "tower_holder" if tower_type == "holder" else tower_type,
        "tower.terrain_style": terrain_type,  # 地形样式
        "pos": position,  # 位置
        "tower.default_rally_pos": tower["rally_point"],  # 默认集结点
        "ui.nav_mesh_id": i,  # 导航网格ID
        "tower.holder_id": i,  # 塔位ID
    }

    return holder_entity


def get_wave_flag(idx, flag):
    """
    创建波次旗帜实体（标记怪物路径起点）

    Args:
        idx (int): 路径编号
        flag (dict): 旗帜数据

    Returns:
        dict: 波次旗帜实体配置
    """
    # 计算旗帜方向（指向路径下一个点）
    dx = flag["pointPosition"]["x"] - flag["position"]["x"]
    dy = flag["pointPosition"]["y"] - flag["position"]["y"]

    entity = {
        "template": "editor_wave_flag",
        "editor.r": math.atan2(dy, dx),  # 旋转角度
        "editor.path_id": idx,  # 路径ID
        "editor.len": 200,  # 旗帜长度
        "pos": flag["position"],  # 位置
    }

    return entity


def get_obj_repeat_forever_entity(obj):
    """
    创建循环特效实体

    Args:
        obj (dict): 特效对象数据

    Returns:
        dict: 特效实体配置
    """
    entity = {"template": "fx_repeat_forever"}

    # 位置
    if "position" in obj and isinstance(obj["position"], dict):
        x, y = obj["position"]["x"], obj["position"]["y"]
        entity["pos"] = {"x": x, "y": y}

    # 锚点（贴图对齐点）
    if "anchor" in obj:
        x, y = obj["anchor"]["x"], obj["anchor"]["y"]
        entity["render.sprites[1].anchor.x"] = x
        entity["render.sprites[1].anchor.y"] = y

    # 缩放
    if "scale" in obj:
        scale = obj["scale"]
        if "x" in scale:
            x, y = scale["x"], scale["y"]
            entity["render.sprites[1].scale.x"] = x
            entity["render.sprites[1].scale.y"] = y
        else:
            entity["render.sprites[1].scale.x"] = scale
            entity["render.sprites[1].scale.y"] = scale

    # 渲染层级
    if "layer" in obj:
        layer = obj["layer"]
        if layer == "decals":
            entity["render.sprites[1].z"] = "Z_DECALS"  # 装饰层
        elif layer == "entities":
            entity["render.sprites[1].z"] = "Z_OBJECTS"  # 对象层

    # Y轴位置调整
    if "y_position_adjust" in obj:
        entity["render.sprites[1].sort_y_offset"] = obj["y_position_adjust"] * -1

    # 静态贴图
    if "single_frame" in obj:
        filename = obj["single_frame"].split(".")[0]
        entity["render.sprites[1].name"] = filename
        entity["render.sprites[1].animated"] = False  # 非动画

    # 动画设置
    if "animations" in obj:
        animations = obj["animations"]
        if "animations_file" in animations:
            sprite_name = re.sub(r"^Stage_\d+_", "", animations["animations_file"])
            # 提取动画名称并添加_run后缀
            entity["render.sprites[1].name"] = (
                f"{re.sub(r"_animations\.plist$", "", sprite_name)}_run"
            )
            entity["render.sprites[1].animated"] = True  # 启用动画

        # 动画延迟参数
        if "max_delay" in animations:
            entity["max_delay"] = animations["max_delay"]
        if "min_delay" in animations:
            entity["min_delay"] = animations["min_delay"]
        if "random_shift" in animations:
            entity["random_shift"] = animations["random_shift"]

    return entity


def get_common_obj_entities(obj, obj_type):
    """
    创建普通对象实体（防御点、旗帜等）

    Args:
        obj (dict): 对象数据
        obj_type (str): 对象类型

    Returns:
        list: 实体配置列表
    """
    entities = []

    # 处理多个位置的情况
    positions = obj["position"]
    if isinstance(positions, dict):
        positions = [positions]

    # 处理多个层级的情况
    layers = obj.get("layer", [])
    if isinstance(layers, str):
        layers = [layers]

    # 根据位置和层级的最大数量创建实体
    max_count = max(len(positions), len(layers)) if (positions or layers) else 1
    for i in range(max_count):
        if obj_type == "defense_point":
            # 防御点实体
            entity = {
                "template": "decal_defend_point5",
                "editor.flip": 0,  # 是否翻转
                "editor.exit_id": 1,  # 退出点ID
                "editor.alpha": 10,  # 透明度
                "editor.orientation": 1,  # 方向
            }
            if i < len(positions):
                entity["pos"] = positions[i]
        else:
            # 其他实体
            entity = {
                "template": (
                    "decal_defense_flag5" if obj_type == "defense_flag" else obj_type
                )
            }

            if i < len(positions):
                entity["pos"] = positions[i]

            # 设置渲染层级
            if i < len(layers):
                z = "Z_DECALS" if layers[i] == "decals" else "Z_OBJECTS"
                entity["render.sprites[1].z"] = z

            if obj_type == "defense_flag":
                entity["editor.flip"] = 0  # 旗帜翻转
                entity["editor.tag"] = 0  # 标签

        entities.append(entity)

    return entities


def get_level_nav_mesh(entities_list):
    """
    生成导航网格（塔位之间的连接关系）

    为每个塔位计算上下左右四个方向最近的邻居

    Args:
        entities_list (list): 实体列表

    Returns:
        list: 导航网格，每个塔位有4个邻居ID（或"nil"）
    """
    nav_mesh = []
    # 筛选出塔位实体
    tower_entities = [e for e in entities_list if "ui.nav_mesh_id" in e]
    entities_by_id = {int(e["ui.nav_mesh_id"]): e for e in tower_entities}

    for entity in tower_entities:
        entity_id = int(entity["ui.nav_mesh_id"])
        x, y = entity["pos"]["x"], entity["pos"]["y"]

        # 初始化四个方向的最近邻居
        directions = {
            "right": (float("inf"), None),  # 右
            "top": (float("inf"), None),  # 上
            "left": (float("inf"), None),  # 左
            "bottom": (float("inf"), None),  # 下
        }

        # 寻找每个方向最近的邻居
        for other_id, other_entity in entities_by_id.items():
            if other_id == entity_id:
                continue

            other_x, other_y = other_entity["pos"]["x"], other_entity["pos"]["y"]
            dx, dy = other_x - x, other_y - y
            distance = math.sqrt(dx**2 + dy**2)

            # 判断方向并更新最近邻居
            if dx > 0 and abs(dy) < abs(dx) and distance < directions["right"][0]:
                directions["right"] = (distance, other_id)
            elif dy > 0 and abs(dy) > abs(dx) and distance < directions["top"][0]:
                directions["top"] = (distance, other_id)
            elif dx < 0 and abs(dy) < abs(dx) and distance < directions["left"][0]:
                directions["left"] = (distance, other_id)
            elif dy < 0 and abs(dy) > abs(dx) and distance < directions["bottom"][0]:
                directions["bottom"] = (distance, other_id)

        # 添加到导航网格
        nav_mesh.append(
            [
                directions["right"][1] or "nil",
                directions["top"][1] or "nil",
                directions["left"][1] or "nil",
                directions["bottom"][1] or "nil",
            ]
        )

    return nav_mesh


def extract_paths_data(plist_data, main_data):
    """
    提取关卡路径数据

    Args:
        plist_data (dict): 从Plist文件解析出的数据
        main_data (dict): 当前关卡的主要数据

    Returns:
        dict: 路径数据，包含连接、路径、曲线、活动路径等信息
    """
    level_data = main_data["level_data"]
    entities_list = level_data["entities_list"]
    level_data["invalid_path_ranges"] = []
    invalid_path_ranges = level_data["invalid_path_ranges"]

    data = {
        "connections": [],  # 路径连接关系
        "paths": [],  # 原始路径节点
        "curves": [],  # 采样后的路径曲线
        "active_paths": [],  # 哪些路径是活动的
    }

    # 遍历所有路径组
    for path_idx, path_group in enumerate(plist_data["paths_pc"]):
        # 1. 处理原始路径数据
        path_nodes = get_origin_paths(path_group)
        if path_nodes:
            data["paths"].append(path_nodes)
            data["active_paths"].append(True)  # 默认所有路径都激活

        # 2. 处理路径曲线（用于怪物寻路）
        first_subpath = path_group["subpaths"][0]
        curves = get_level_path_curves(first_subpath)
        data["curves"].append(curves)

        # 3. 检查是否有change_node信息（传送点等特殊路径修改）
        for segment in path_group["metadata"].get("segments", []):
            for modifier in segment.get("modifier", []):
                if modifier.get("key") != "change_node":
                    continue

                # 添加传送点实体
                entity = get_change_node_entity(path_idx + 1, modifier)
                entities_list.append(entity)

                # 记录无效路径范围（怪物传送时会跳过）
                invalid_range = get_invalid_path_ranges(path_idx + 1, modifier)
                invalid_path_ranges.append(invalid_range)

    return data


def get_origin_paths(path_group):
    """
    提取原始路径节点

    Args:
        path_group (dict): 路径组数据

    Returns:
        list: 路径节点列表，每个子路径是一系列点
    """
    path_nodes = []

    for subpath in path_group["subpaths"]:
        points = [{"x": float(p["x"]), "y": float(p["y"])} for p in subpath]
        path_nodes.append(points)

    return path_nodes


def get_level_path_curves(first_subpath):
    """
    创建路径曲线数据（采样版本）

    对路径进行采样，减少数据量，提高寻路效率
    采样策略：首点 + 每隔8点 + 末点

    Args:
        first_subpath (list): 第一个子路径的所有点

    Returns:
        dict: 包含采样节点和宽度的曲线数据
    """
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

    # 计算widths长度（路径宽度）
    widths_length = (len(sampled_nodes) - 1) // 3 + 1
    widths = [40] * widths_length  # 默认宽度40像素

    return {"nodes": sampled_nodes, "widths": widths}


def get_change_node_entity(path_idx, modifier):
    """
    创建传送点实体

    Args:
        path_idx (int): 路径编号
        modifier (dict): 修改器数据

    Returns:
        dict: 传送点实体配置
    """
    return {
        "template": "controller_teleport_enemies",
        "path": path_idx,  # 所在路径
        "start_ni": int(modifier["from"]) + 1,  # 传送起始节点索引
        "end_ni": int(modifier["to"]) + 1,  # 传送目标节点索引
        "duration": float(modifier["duration"]),  # 传送时间
    }


def get_invalid_path_ranges(path_idx, modifier):
    """
    获取无效路径范围

    Args:
        path_idx (int): 路径编号
        modifier (dict): 修改器数据

    Returns:
        dict: 无效路径范围数据
    """
    return {
        "from": int(modifier["from"]) + 1,  # 起始节点
        "to": int(modifier["to"]) + 1,  # 结束节点
        "path_id": path_idx,  # 路径ID
    }


def extract_grids_data(plist_data):
    """
    提取关卡网格数据（地形单元格）

    Args:
        plist_data (dict): 从Plist文件解析出的数据

    Returns:
        dict: 网格数据，包含原点、单元格大小和网格数组
    """
    columns = get_grid_columns(plist_data)

    # 计算最大行列数
    max_column = 0
    max_row = 0
    for cell in plist_data["grid_pc"]:
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
    max_rows_in_grid = max(len(cells) for cells in columns.values()) if columns else 0

    # 构建网格数组
    for column in range(max_column + 1):
        if column in columns:
            # 对该列的数据按行号降序排序
            cells = sorted(columns[column], key=lambda x: x[0], reverse=True)
            # 转换地形类型：2→257（不可建造），其他→1（可建造）
            column_data = [257 if terrain == 2 else 1 for (row, terrain) in cells]
        else:
            # 空列：用1填充（可建造区域）
            column_data = [1] * max_rows_in_grid

        grids.append(column_data)

    return {
        "ox": -170.5,  # 网格原点X
        "oy": -48,  # 网格原点Y
        "cell_size": 17.0625,  # 单元格大小
        "grid": grids,  # 网格数据
    }


def get_grid_columns(plist_data):
    """
    按列组织网格数据

    Args:
        plist_data (dict): 从Plist文件解析出的数据

    Returns:
        dict: 按列分组的网格数据
    """
    columns = {}

    for cell in plist_data["grid_pc"]:
        column = int(cell["column"])
        row = int(cell["row"])
        terrain_type = int(cell["terrainType"])

        if column not in columns:
            columns[column] = []

        columns[column].append((row, terrain_type))

    return columns


def extract_waves_data(plist_data):
    """
    提取波次数据（常规怪物波次）

    Args:
        plist_data (dict): 从Plist文件解析出的数据

    Returns:
        dict: 波次数据，包含金币、波次列表等信息
    """
    data = {
        "cash": plist_data["gold"],  # 初始金币
        "groups": [],
    }

    # 处理每个波次
    for wave in plist_data["waves"]:
        new_wave = {"wave_interval": wave["interval"], "spawns": []}

        # 处理每个出怪组
        for spawns in wave["subwaves"]:
            new_spawns = {
                "delay": spawns["interval"],  # 延迟时间
                "path_index": spawns["path_index"] + 1,  # 路径索引
                "spawns": [],  # 怪物列表
            }

            # 处理每个怪物生成点
            for spawn in spawns["spawns"]:
                new_spawn = {
                    "creep": "enemy_" + spawn["enemy"],  # 怪物类型
                    "max": spawn["cant"],  # 总数量
                    "max_same": 0,  # 同时存在的最大数量
                    "interval": spawn["interval"],  # 生成间隔
                    "subpath": (
                        0
                        if spawn["fixed_sub_path"] < 0
                        else spawn["fixed_sub_path"] + 1
                    ),
                    "interval_next": spawn["interval_next_spawn"],  # 下一批延迟
                }

                new_spawns["spawns"].append(new_spawn)
            new_wave["spawns"].append(new_spawns)
        data["groups"].append(new_wave)

    return data


def extract_spawners_data(spawner_data_name, plist_data, main_data, num_level_mode):
    """
    获取自定义刷怪点数据

    Args:
        spawner_data_name (str): 刷怪点数据文件名
        plist_data (dict): 从Plist文件解析出的数据
        main_data (dict): 当前关卡的主要数据
        num_level_mode (int): 关卡模式的数字表示

    Returns:
        dict: 刷怪点数据，包含点、组、波次等信息
    """
    data = {}

    # 处理刷怪点实体
    entities = handle_spawners_entities(
        plist_data, main_data, spawner_data_name, num_level_mode
    )

    # 获取刷怪点位置
    positions = get_spawners_positions(plist_data)

    # 转换为点数据
    points = get_spawners_points(positions)

    # 组装数据
    data["points"] = points
    data["groups"] = get_spawners_groups(points, entities)
    data["waves"] = get_spawners_waves(plist_data, points)

    return data


def get_num_level_mode(level_mode):
    """
    将关卡模式名称转换为数字代号，0-based索引

    Args:
        level_mode (str): 关卡模式名称

    Returns:
        int: 关卡模式对应的数字
            0 - campaign（战役模式）
            1 - heroic（英雄模式）
            2 - iron（铁拳模式）
    """
    if level_mode == "campaign":
        return 0
    if level_mode == "heroic":
        return 1
    if level_mode == "iron":
        return 2


def handle_spawners_entities(plist_data, main_data, spawner_data_name, num_level_mode):
    """
    处理刷怪点相关实体

    Args:
        plist_data (dict): 从Plist文件解析出的数据
        main_data (dict): 当前关卡的主要数据
        spawner_data_name (str): 刷怪点数据文件名
        num_level_mode (int): 关卡模式的数字表示

    Returns:
        dict: 按类型分组的实体数据
    """
    num_level_mode = num_level_mode + 1
    level_data_entities = main_data["level_data"]["entities_list"]

    entities = {"spawners": [], "repeat_forever": [], "else": []}

    # 1. 处理 custom_spawners.objects（刷怪点对象）
    objects = plist_data["custom_spawners"].get("objects", [])
    for i, obj in enumerate(objects, 1):
        custom_spawner_entity = get_custom_spawners_entity(i, obj, num_level_mode)
        entities["spawners"].append(custom_spawner_entity)
        level_data_entities.append(custom_spawner_entity)

    # 2. 添加 mega_spawner 实体（主刷怪控制器）
    mega_spawner = get_mega_spawner(spawner_data_name, num_level_mode)
    entities["else"].append(mega_spawner)
    level_data_entities.append(mega_spawner)

    # 3. 处理普通 objects（非刷怪点相关）
    objects = plist_data.get("objects", [])
    for obj in objects:
        obj_type = obj.get("key", obj.get("type", ""))

        if obj_type == "fx_repeat_forever":
            repeat_forever_entity = get_obj_repeat_forever_entity(obj)
            entities["repeat_forever"].append(repeat_forever_entity)
            level_data_entities.append(repeat_forever_entity)

        elif obj_type:
            common_entities = get_common_obj_entities(obj, obj_type)
            entities["else"] += common_entities
            level_data_entities += common_entities

    return entities


def get_custom_spawners_entity(i, obj, num_level_mode):
    """
    创建自定义刷怪点实体

    Args:
        i (int): 对象编号
        obj (dict): 对象数据
        num_level_mode (int): 关卡模式的数字表示

    Returns:
        dict: 刷怪点实体配置
    """
    entity = {
        "template": obj["type"],  # 实体模板
        "pos": obj["position"],  # 位置
        "spawner.name": f"object{i}",  # 刷怪点名称
        "editor.game_mode": num_level_mode,  # 游戏模式
    }

    return entity


def get_mega_spawner(spawner_data_name, num_level_mode):
    """
    创建主刷怪控制器实体

    Args:
        spawner_data_name (str): 刷怪点数据文件名
        num_level_mode (int): 关卡模式的数字表示

    Returns:
        dict: 主刷怪控制器配置
    """
    return {
        "template": "mega_spawner",  # 模板类型
        "load_file": spawner_data_name.replace(".lua", ""),  # 加载的数据文件
        "editor.game_mode": num_level_mode,  # 游戏模式
    }


def get_spawners_positions(plist_data):
    """
    提取所有自定义刷怪点的位置

    Args:
        plist_data (dict): 从Plist文件解析出的数据

    Returns:
        list: 位置列表，每个位置包含路径、x、y坐标
    """
    positions = []
    events = plist_data["custom_spawners"]["events"]

    # 遍历所有波次事件
    for wave in events.values():
        for event in wave:
            config = event["config"]
            path = config["path"] + 1  # 转换为1-based

            # 提取每个刷怪点的位置
            for spawn in config["spawns"]:
                position = spawn["position"]
                x, y = position["x"], position["y"]

                if x and y and path:
                    positions.append({"path": path, "x": x, "y": y})

    return positions


def get_spawners_points(positions):
    """
    将位置转换为唯一的点数据

    Args:
        positions (list): 位置列表

    Returns:
        list: 唯一的点数据列表
    """
    seen = set()
    unique_positions = []

    # 去重
    for pos in positions:
        key = (pos["x"], pos["y"], pos["path"])
        if key not in seen:
            seen.add(key)
            unique_positions.append(pos)

    # 转换为点格式
    points = []
    for pos in unique_positions:
        points.append(
            {
                "path": pos["path"],
                "from": {"x": pos["x"], "y": pos["y"]},  # 起始点
                "to": {"x": pos["x"], "y": pos["y"]},  # 结束点（同一点）
            }
        )

    return points


def get_spawners_groups(points, entities):
    """
    创建刷怪点分组

    Args:
        points (list): 点数据
        entities (dict): 实体数据

    Returns:
        list: 分组列表，包含数字组和命名组
    """
    spawner_entities = entities["spawners"]
    groups = []

    # 1. 为每个点创建数字组 {1}, {2}...
    for i in range(1, len(points) + 1):
        groups.append([f"{i}", [i]])

    # 2. 为每个刷怪点实体创建命名组 {som1: ["object1"]}, ...
    for i, entity in enumerate(spawner_entities, 1):
        groups.append([f"som{i}", [entity["spawner.name"]]])

    return groups


def get_spawners_waves(plist_data, points):
    """
    创建刷怪点波次数据

    Args:
        plist_data (dict): 从Plist文件解析出的数据
        points (list): 点数据

    Returns:
        dict: 波次数据，按波次编号组织
    """
    events = plist_data["custom_spawners"]["events"]
    waves = {}

    for wave_name, wave_events in events.items():
        # 提取波次编号
        wave_num = re.search(r"\d+$", wave_name).group()
        wave_entries = []

        for event in wave_events:
            delay = event["delay"]
            obj = event.get("object")  # 关联的刷怪点对象

            config = event["config"]
            spawns = config["spawns"]
            path = config["path"] + 1
            interval_spawns = config["interval_spawns"]

            # 如果有刷怪点对象，先添加对象表
            if obj is not None:
                wave_entries.append(
                    [
                        delay,
                        0,
                        f"som{obj+1}",  # 对象组名
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

            # 计算刷怪延迟（如果有对象，加上额外延迟）
            spawn_delay = (
                delay + setting["custom_spawners_delay"] if obj is not None else delay
            )

            # 添加刷怪点数据
            for i in range(len(spawns)):
                # 找出对应的点索引
                point_index = None
                spawn = spawns[i]
                spawn_pos = spawn["position"]
                spawn_x, spawn_y = spawn_pos["x"], spawn_pos["y"]

                # 匹配点数据
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
                        point_index,  # 点索引
                        spawn["subpath"] + 1,  # 子路径
                        cant,  # 数量
                        False,  # 是否循环
                        True,  # 是否激活
                        interval,  # 间隔
                        interval,  # 最小间隔
                        "enemy_" + spawn["type"],  # 怪物类型
                    ]
                )

                # 计算下一批刷怪的延迟
                duration = (cant - 1) * interval
                if duration < 0:
                    duration = 0
                spawn_delay += duration + interval_spawns

        waves[wave_num] = wave_entries

    return waves


def write_lua_files():
    """
    将所有数据写入Lua文件

    创建以下目录结构：
    output/
        ├── levels/     # 关卡相关文件
        └── waves/      # 波次文件
    """
    levels_dir = config.output_path / "levels"
    waves_dir = config.output_path / "waves"
    levels_dir.mkdir(exist_ok=True)
    waves_dir.mkdir(exist_ok=True)

    # 遍历每个关卡的数据
    for level_num, datas in main_datas.items():
        write_level_data_file(datas["level_data"], levels_dir)
        write_paths_data_file(datas["paths_data"], levels_dir)
        write_grids_data_file(datas["grids_data"], levels_dir)
        write_waves_data_file(datas["waves_data"], waves_dir)
        write_spawners_data_file(datas["spawners_data"], levels_dir)


def write_level_data_file(level_data, levels_dir):
    """
    写入关卡数据文件

    Args:
        level_data (dict): 关卡数据
        levels_dir (Path): 输出目录
    """
    lua_content = write_level_data_template.render(level_data)
    file = level_data["name"]

    log.info(f"写入关卡数据{file}...")

    with open(levels_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def write_paths_data_file(paths_data, levels_dir):
    """
    写入路径数据文件

    Args:
        paths_data (dict): 路径数据
        levels_dir (Path): 输出目录
    """
    lua_content = write_paths_data_template.render(paths_data)
    file = paths_data["name"]

    log.info(f"写入路径数据{file}...")

    with open(levels_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def write_grids_data_file(grids_data, levels_dir):
    """
    写入网格数据文件

    Args:
        grids_data (dict): 网格数据
        levels_dir (Path): 输出目录
    """
    lua_content = write_grids_data_template.render(grids_data)
    file = grids_data["name"]

    log.info(f"写入网格数据{file}...")

    with open(levels_dir / file, "w", encoding="utf-8") as f:
        f.write(lua_content)


def write_waves_data_file(waves_data, waves_dir):
    """
    写入波次数据文件

    Args:
        waves_data (list): 波次数据列表
        waves_dir (Path): 输出目录
    """
    for waves_data in waves_data:
        if not waves_data:
            continue

        lua_content = write_waves_data_template.render(waves_data)

        file = waves_data["name"]
        log.info(f"写入波次数据{file}...")

        with open(waves_dir / file, "w", encoding="utf-8") as f:
            f.write(lua_content)


def write_spawners_data_file(spawners_data, levels_dir):
    """
    写入刷怪点数据文件

    Args:
        spawners_data (list): 刷怪点数据列表
        levels_dir (Path): 输出目录
    """
    for spawners_data in spawners_data:
        if not spawners_data:
            continue

        lua_content = write_spawners_data_template.render(spawners_data)
        file = spawners_data["name"]

        log.info(f"写入特殊出怪数据{file}...")

        with open(levels_dir / file, "w", encoding="utf-8") as f:
            f.write(lua_content)


def get_input_files():
    """
    获取输入目录中的所有Plist文件

    Returns:
        list: 文件数据列表，每个元素是(file, level_num, level_mode, plist_data)元组
    """
    level_data_files = []
    waves_data_files = []

    # 扫描输入目录
    for file in config.input_path.iterdir():
        if file.suffix != ".plist":
            log.info(f"跳过无效文件 {file.name}")
            continue

        # 匹配文件名模式：level数字_模式.plist
        match = re.match(r"level(\d+)_(campaign|heroic|iron|data)", file.stem)
        if match:
            try:
                with open(file, "rb") as f:
                    plist_data = plistlib.load(f)

                level_num, level_mode = match.group(1), match.group(2)

                log.info(f"📖 读取文件: {file.name}")

                file_data = (level_num, level_mode, plist_data)

                # 按类型分类
                if level_mode == "data":
                    level_data_files.append(file_data)
                elif level_mode:
                    waves_data_files.append(file_data)

            except Exception as e:
                log.error(f"❌ 读取文件失败: {file.name} - {traceback.print_exc()}")
                continue

    # 合并文件列表（关卡数据在前，波次数据在后）
    files = level_data_files + waves_data_files

    return files


def main():
    """
    主函数：执行Plist到Lua的转换

    Returns:
        bool: 转换是否成功
    """
    global setting
    setting = config.setting["plist_level_to_lua"]

    try:
        # 获取输入文件
        files = get_input_files()
        if not files:
            log.warning("⚠️ 未找到需要转换的Plist文件")
            return False

        log.info(f"🔧 找到 {len(files)} 个文件待转换")

        # 处理所有文件
        for level_num, level_mode, plist_data in files:
            level_num = str(level_num).zfill(setting["level_name_leading_zero"])

            get_lua_data(level_num, level_mode, plist_data)

        # 对实体按模板名称排序（便于调试和阅读）
        for level_num, datas in main_datas.items():
            level_data_entities = datas["level_data"]["entities_list"]
            level_data_entities.sort(key=lambda x: x["template"])

        # 写入所有文件
        write_lua_files()

        log.info("✅ 所有文件转化完毕")
        return True

    except Exception as e:
        log.error(f"❌ 转换过程出错: {traceback.print_exc()}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 设置全局异常处理
    import sys

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """全局异常处理器"""
        log.critical("未处理的异常", exc_info=(exc_type, exc_value, exc_traceback))
        sys.exit(1)

    sys.excepthook = global_exception_handler

    # 执行主函数
    success = main()
    exit(0 if success else 1)