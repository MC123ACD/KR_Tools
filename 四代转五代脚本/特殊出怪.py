import plistlib
import sys
import os
import re

def extract_positions_from_plist(plist_path):
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f)
	
	positions = []
	events = plist_data.get('custom_spawners', {}).get('events', {})
	
	for wave in events.values():
		for event in wave:
			config = event.get('config', {})
			path = config.get('path', -1) + 1  # 路径索引从1开始
			
			for spawn in config.get('spawns', []):
				position = spawn.get('position', {})
				x, y = position.get('x', 0), position.get('y', 0)
				
				if x and y and path:
					positions.append({
						'path': path,
						'x': x,
						'y': y
					})
	
	return positions

def extract_objects_from_plist(plist_path):
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f)
	
	# 第一部分：处理 custom_spawners.objects
	objects = plist_data.get('custom_spawners', {}).get('objects', [])
	spawner_entities = []  # 仅来自 custom_spawners.objects 的实体
	all_entities = []      # 所有实体（包括后续添加的）
	
	base_name = os.path.basename(plist_path)
	game_mode = None
	if '_campaign.plist' in base_name:
		game_mode = 1
	elif '_heroic.plist' in base_name:
		game_mode = 2
	elif '_iron.plist' in base_name:
		game_mode = 3
	
	# 添加spawner对象（custom_spawners.objects）
	for i, obj in enumerate(objects, 1):
		entity = {
			'template': obj.get('type', ''),
			'pos': obj.get('position', {'x': 0, 'y': 0}),
			'spawner.pi': 1,
			'spawner.name': f'object{i}'
		}
		if game_mode is not None:
			entity['editor.game_mode'] = game_mode
		spawner_entities.append(entity)
		all_entities.append(entity)
	
	# 第二部分：处理 events 添加的 mega_spawner
	events = plist_data.get('custom_spawners', {}).get('events', {})
	if events:
		match = re.match(r'level(\d+)_(.+)\.plist', base_name)
		if match:
			load_file = f"level4{match.group(1)}{match.group(2)}_spawner"  # 修改为level4前缀
			mega_spawner = {
				'template': 'mega_spawner',
				'load_file': load_file
			}
			if game_mode is not None:
				mega_spawner['editor.game_mode'] = game_mode
			all_entities.append(mega_spawner)
	
	# 第三部分：处理普通 objects（非 custom_spawners.objects）
	objects = plist_data.get('objects', [])
	for obj in objects:
		obj_type = obj.get('key', obj.get('type', ''))
		
		if obj_type == 'fx_repeat_forever':
			lua_entity = {'template': 'fx_repeat_forever'}
			
			if 'position' in obj and isinstance(obj['position'], dict):
				x, y = obj['position']['x'], obj['position']['y']
				lua_entity['pos'] = {'x': x, 'y': y}
			
			if 'anchor' in obj:
				x, y = obj['anchor']['x'], obj['anchor']['y']
				lua_entity['render.sprites[1].anchor.x'] = x
				lua_entity['render.sprites[1].anchor.y'] = y
			
			if 'scale' in obj:
				x, y = obj['scale']['x'], obj['scale']['y']
				lua_entity['render.sprites[1].scale.x'] = x
				lua_entity['render.sprites[1].scale.y'] = y
			
			if 'layer' in obj:
				layer = obj['layer']
				if layer == 'decals':
					lua_entity['render.sprites[1].z'] = 'Z_DECALS'
				elif layer == 'entities':
					lua_entity['render.sprites[1].z'] = 'Z_OBJECTS'
			
			if 'single_frame' in obj:
				filename = obj['single_frame'].replace('.png', '')
				lua_entity['render.sprites[1].name'] = filename
				lua_entity['render.sprites[1].animated'] = False
			
			if 'animations' in obj:
				animations = obj['animations']
				if 'animations_file' in animations:
					anim_file = animations['animations_file']
					base_name = re.sub(r'_animations\.plist$', '', anim_file)
					lua_entity['render.sprites[1].name'] = f"{base_name}_run"
					lua_entity['render.sprites[1].animated'] = True
				
				if 'max_delay' in animations:
					lua_entity['max_delay'] = animations['max_delay']
				if 'min_delay' in animations:
					lua_entity['min_delay'] = animations['min_delay']
				if 'random_shift' in animations:
					lua_entity['random_shift'] = animations['random_shift']

			all_entities.append(lua_entity)
		
		elif obj_type:
			positions = obj.get('position', [])
			if isinstance(positions, dict):
				positions = [positions]
			
			layers = obj.get('layer', [])
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
						"editor.orientation": 1
					}
					if i < len(positions):
						entity["pos"] = positions[i]
					all_entities.append(entity)
				else:
					entity = {"template": "decal_defense_flag5" if obj_type == "defense_flag" else obj_type}
					
					if i < len(positions):
						entity["pos"] = positions[i]
					
					if i < len(layers):
						z = 'Z_DECALS' if layers[i] == 'decals' else 'Z_OBJECTS'
						entity["render.sprites[1].z"] = z
					
					if obj_type == "defense_flag":
						entity["editor.flip"] = 0
						entity["editor.tag"] = 0
					
					all_entities.append(entity)

	return spawner_entities, all_entities

def generate_lua_points(positions):
	seen = set()
	unique_positions = []
	
	for pos in positions:
		key = (pos['x'], pos['y'], pos['path'])
		if key not in seen:
			seen.add(key)
			unique_positions.append(pos)
	
	points = []
	for pos in unique_positions:
		points.append({
			'path': pos['path'],
			'from': {'x': pos['x'], 'y': pos['y']},
			'to': {'x': pos['x'], 'y': pos['y']}
		})
	
	return points

def generate_groups(points, spawner_entities):
	groups = []
	
	# 为每个路径点生成数字组 {1}, {2}...
	for i in range(1, len(points) + 1):
		groups.append({i})
	
	# 只为 spawner_entities 生成命名组
	for i, entity in enumerate(spawner_entities, 1):
		groups.append({
			f'som{i}': [entity['spawner.name']]
		})
	
	return groups

def generate_waves(plist_path, points):
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f)
	
	events = plist_data.get('custom_spawners', {}).get('events', {})
	waves = {}
	
	# 确定wave表索引
	base_name = os.path.basename(plist_path)
	wave_index = 1  # 默认
	if '_heroic.plist' in base_name:
		wave_index = 2
	elif '_iron.plist' in base_name:
		wave_index = 3
	
	wave_table = {}
	
	for wave_name, wave_events in events.items():
		# 提取wave编号
		wave_num = int(re.search(r'wave(\d+)', wave_name).group(1))
		
		wave_entries = []
		
		for event in wave_events:
			delay = event.get('delay', 0)
			obj = event.get('object', None)
			config = event.get('config', {})
			spawns = config.get('spawns', [])
			path = config.get('path', -1) + 1
			interval_spawns = config.get('interval_spawns', 0)
			
			# 如果有object，先添加object表
			if obj is not None:
				wave_entries.append([
					delay,
					0,
					f'som{obj+1}',
					None,
					None,
					None,
					None,
					None,
					None,
					"CUSTOM",
					True
				])
			
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
					spawn_pos = spawn.get('position', {})
					spawn_x, spawn_y = spawn_pos.get('x', 0), spawn_pos.get('y', 0)
					for i, point in enumerate(points, 1):
						if (point['path'] == path and 
							point['from']['x'] == spawn_x and 
							point['from']['y'] == spawn_y):
							point_index = i
							break

					if point_index is not None:
						cant = spawn.get('cant', 0)
						interval = spawn.get('interval', 0)
						wave_entries.append([
							spawn_delay,
							0,
							point_index,
							spawn.get('subpath', -1) + 1,
							cant,
							False,
							True,
							interval,
							interval,
							"enemy_" + spawn.get('type', '')
						])
						duration = (cant - 1) * interval
						if duration < 0:
							duration = 0
						spawn_delay += duration + interval_spawns
		
		if wave_entries:
			wave_table[wave_num] = wave_entries
	
	if wave_table:
		waves[wave_index] = wave_table
	return waves

def convert_to_lua(points, entities, groups, waves):
	lua_code = "return {\n"
	
	if entities:
		lua_code += "\tentities_list = {\n"
		for entity in entities:
			lua_code += "\t\t{\n"
			for key, value in entity.items():
				# 检查key是否是有效的Lua标识符（只包含字母数字下划线且不以数字开头）
				is_valid_identifier = re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key)
				formatted_key = f'["{key}"]' if not is_valid_identifier else key
				
				if isinstance(value, dict):
					lua_code += f"\t\t\t{formatted_key} = {{\n"
					lua_code += f"\t\t\t\tx = {value.get('x', 0)},\n"
					lua_code += f"\t\t\t\ty = {value.get('y', 0)}\n"
					lua_code += "\t\t\t},\n"
				else:
					value_str = (
						"nil" if value is None else
						"true" if value is True else
						"false" if value is False else
						f'"{value}"' if isinstance(value, str) and value not in ['Z_DECALS', 'Z_OBJECTS'] else
						str(value)
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
					lua_code += f"\t\t\t\"{name}\",\n"
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
								lua_code += f"\t\t\t\t\t{item and 'true' or 'false'}\n"
							elif isinstance(item, str):
								lua_code += f"\t\t\t\t\t\"{item}\"\n"
							else:
								lua_code += f"\t\t\t\t\t{item}\n"
						else:
							if item is None:
								lua_code += "\t\t\t\t\tnil,\n"
							elif isinstance(item, bool):
								lua_code += f"\t\t\t\t\t{item and 'true' or 'false'},\n"
							elif isinstance(item, str):
								lua_code += f"\t\t\t\t\t\"{item}\",\n"
							else:
								lua_code += f"\t\t\t\t\t{item},\n"
					lua_code += "\t\t\t\t},\n"
				lua_code += "\t\t\t},\n"
			lua_code += "\t\t},\n"
		lua_code += "\t},\n"
	
	lua_code += "}"
	return lua_code

def process_plist_file(plist_path):
	try:
		positions = extract_positions_from_plist(plist_path)
		spawner_entities, all_entities = extract_objects_from_plist(plist_path)
		points = generate_lua_points(positions)
		groups = generate_groups(points, spawner_entities)
		waves = generate_waves(plist_path, points)
		lua_code = convert_to_lua(points, all_entities, groups, waves)
		
		base_name = os.path.basename(plist_path)
		match = re.match(r'level(\d+)_(.+)\.plist', base_name)
		if match:
			# 修改输出文件名为level4XXYYY_spawner.lua格式
			output_name = f"level4{match.group(1)}{match.group(2)}_spawner.lua"
			output_path = os.path.join(os.path.dirname(plist_path), output_name)
			
			with open(output_path, 'w') as f:
				f.write(lua_code)
			print(f"转换成功: {plist_path} -> {output_path}")
		else:
			print(f"跳过不符合命名规则的文件: {plist_path}")
	
	except Exception as e:
		print(f"处理文件 {plist_path} 时出错: {str(e)}")

def main():
	current_dir = os.path.dirname(os.path.abspath(__file__))
	plist_files = [
		f for f in os.listdir(current_dir) 
		if re.match(r'level\d+_.+\.plist$', f)
	]
	
	if not plist_files:
		print("当前目录下未找到符合 levelXX_YYY.plist 模式的plist文件")
		return
	
	for plist_file in plist_files:
		process_plist_file(os.path.join(current_dir, plist_file))
	
	print("所有文件处理完成")

if __name__ == "__main__":
	main()