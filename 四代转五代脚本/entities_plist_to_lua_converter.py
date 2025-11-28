import plistlib
import re
import os
import math
from pathlib import Path

def extract_level_number(filename):
	"""提取文件名中的数字部分，如果无法匹配则返回None"""
	match = re.search(r'level(\d+)_data\.plist$', filename, re.IGNORECASE)
	return match.group(1) if match else None

def calculate_nav_mesh(entities_list):
	nav_mesh = []
	tower_entities = [e for e in entities_list if "ui.nav_mesh_id" in e]
	if not tower_entities:
		return None
		
	entities_by_id = {int(e["ui.nav_mesh_id"]): e for e in tower_entities}

	for entity in tower_entities:
		entity_id = int(entity["ui.nav_mesh_id"])
		x, y = entity["pos"]["x"], entity["pos"]["y"]
		directions = {
			"right": (float('inf'), None),
			"top": (float('inf'), None),
			"left": (float('inf'), None),
			"bottom": (float('inf'), None)
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
			elif dy < 0 and abs(dy) > abs(dx) and distance < directions["bottom"][0]:
				directions["bottom"] = (distance, other_id)
		
		nav_mesh.append([
			directions["right"][1] or "nil",
			directions["top"][1] or "nil",
			directions["left"][1] or "nil",
			directions["bottom"][1] or "nil"
		])
	
	return nav_mesh

def create_background_entity(level_number):
	return {
		"template": "decal_background",
		"render.sprites[1].z": 1000,
		"render.sprites[1].name": f"stage_4{level_number}",
		"pos": {"x": 512, "y": 384}
	}

def process_plist_data(plist_data, level_number):
	entities_list = [create_background_entity(level_number)]
	terrain = plist_data.get('terrain', 1)

	if 'towers' in plist_data:
		for i, tower in enumerate(plist_data['towers'], 1):
			tower_type = tower.get('type', '')
			position = tower.get('position', {})
			if 'y' in position:
				position['y'] -= 13
			entity = {
				"template": "tower_holder" if tower_type == 'holder' else tower_type,
				"tower.terrain_style": terrain + 400,
				"pos": position,
				"tower.default_rally_pos": tower.get('rally_point', {}),
				"ui.nav_mesh_id": str(i),
				"tower.holder_id": str(i),
			}
			entities_list.append(entity)

	if 'waveFlags_pc' in plist_data:
		for idx, flag in enumerate(plist_data['waveFlags_pc'], 1):
			dx = flag['pointPosition']['x'] - flag['position']['x']
			dy = flag['pointPosition']['y'] - flag['position']['y']
			entities_list.append({
				'editor.r': math.atan2(dy, dx),
				'editor.path_id': idx,
				'template': 'editor_wave_flag',
				'editor.len': 200,
				'pos': flag['position']
			})
	
	if 'objects' in plist_data:
		for obj in plist_data['objects']:
			obj_type = obj.get('key', obj.get('type', ''))
			if not obj_type:
				continue
				
			if obj_type == 'fx_repeat_forever':
				entity = {'template': 'fx_repeat_forever'}
				
				if 'position' in obj and isinstance(obj['position'], dict):
					x, y = obj['position']['x'], obj['position']['y']
					entity['pos'] = {'x': x, 'y': y}
				
				if 'anchor' in obj:
					x, y = obj['anchor']['x'], obj['anchor']['y']
					entity['render.sprites[1].anchor.x'] = x
					entity['render.sprites[1].anchor.y'] = y
				
				if 'scale' in obj:
					x, y = obj['scale']['x'], obj['scale']['y']
					entity['render.sprites[1].scale.x'] = x
					entity['render.sprites[1].scale.y'] = y

				if 'scale' in obj:
					scale = obj['scale']
					if 'x' in scale:
						x, y = scale['x'], scale['y']
						entity['render.sprites[1].scale.x'] = x
						entity['render.sprites[1].scale.y'] = y
					else:
						entity['render.sprites[1].scale.x'] = scale
						entity['render.sprites[1].scale.y'] = scale

				if 'layer' in obj:
					layer = obj['layer']
					if layer == 'decals':
						entity['render.sprites[1].z'] = 'Z_DECALS'
					elif layer == 'entities':
						entity['render.sprites[1].z'] = 'Z_OBJECTS'

				if 'y_position_adjust' in obj:
					entity['render.sprites[1].sort_y_offset'] = obj['y_position_adjust'] * -1

				if 'single_frame' in obj:
					filename = obj['single_frame'].replace('.png', '')
					entity['render.sprites[1].name'] = filename
					entity['render.sprites[1].animated'] = False
				
				if 'animations' in obj:
					animations = obj['animations']
					if 'animations_file' in animations:
						anim_file = animations['animations_file']
						base_name = re.sub(r'_animations\.plist$', '', anim_file)
						entity['render.sprites[1].name'] = f"{base_name}_run"
						entity['render.sprites[1].animated'] = True
					
					if 'max_delay' in animations:
						entity['max_delay'] = animations['max_delay']
					if 'min_delay' in animations:
						entity['min_delay'] = animations['min_delay']
					if 'random_shift' in animations:
						entity['random_shift'] = animations['random_shift']
				
				entities_list.append(entity)
			else:
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
						entities_list.append(entity)
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
						
						entities_list.append(entity)
	
	return entities_list, terrain

def generate_lua_file(entities_list, terrain, level_number, nav_mesh=None, hero_positions=None):
	content = [
		"return {",
		f"\tlevel_terrain_type = {terrain + 400},",
		"\tlocked_hero = false,",
		"\tmax_upgrade_level = 5,",
		"\tcustom_start_pos = {",
		"\t\tzoom = 1.3,",
		"\t\tpos = {x = 512, y = 384}",
		"\t},"
	]

	if hero_positions:
		content.append("\tcustom_spawn_pos = {")
		for pos in hero_positions:
			content.append("\t\t{")
			content.append("\t\t\tpos = {")
			content.append(f"\t\t\t\tx = {pos.get('x', 0)},")
			content.append(f"\t\t\t\ty = {pos.get('y', 0)}")
			content.append("\t\t\t}")
			content.append("\t\t},")
		content.append("\t},")

	content.append("\tentities_list = {")
	for entity in entities_list:
		content.append("\t\t{")
		for key, value in entity.items():
			# 检查key是否是有效的Lua标识符（只包含字母数字下划线且不以数字开头）
			is_valid_identifier = re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key)
			formatted_key = f'["{key}"]' if not is_valid_identifier else key
			
			if isinstance(value, dict):
				content.append(f"\t\t\t{formatted_key} = {{")
				content.append(f"\t\t\t\tx = {value.get('x', 0)},")
				content.append(f"\t\t\t\ty = {value.get('y', 0)}")
				content.append("\t\t\t},")
			else:
				value_str = (
					"nil" if value is None else
					"true" if value is True else
					"false" if value is False else
					f'"{value}"' if isinstance(value, str) and value not in ['Z_DECALS', 'Z_OBJECTS'] else
					str(value)
				)
				content.append(f"\t\t\t{formatted_key} = {value_str},")
		content.append("\t\t},")
	content.append("\t},")

	if nav_mesh:
		content.append("\tnav_mesh = {")
		for mesh in nav_mesh:
			content.append(f"\t\t{{ {', '.join(str(i) for i in mesh)} }},")
		content.append("\t}")

	content.append("}")
	return "\n".join(content)

def convert_plist_to_lua(plist_path):
	try:
		with open(plist_path, 'rb') as f:
			plist_data = plistlib.load(f)
		
		level_number = extract_level_number(plist_path.name)
		if level_number is None:
			print(f"跳过 {plist_path.name}: 文件名不符合levelXX_data.plist格式")
			return False
		
		entities_list, terrain = process_plist_data(plist_data, level_number)
		
		nav_mesh = calculate_nav_mesh(entities_list)
		
		hero_positions = []
		if 'hero_position' in plist_data and isinstance(plist_data['hero_position'], dict):
			hero_positions.append(plist_data['hero_position'])
		
		lua_content = generate_lua_file(
			entities_list, terrain, level_number, nav_mesh, hero_positions
		)
		
		output_path = plist_path.parent / f"level4{level_number}_data.lua"
		with open(output_path, 'w', encoding='utf-8') as f:
			f.write(lua_content)
		
		print(f"成功转换: {plist_path.name} -> {output_path.name}")
		return True
	
	except Exception as e:
		print(f"转换失败 {plist_path.name}: {str(e)}")
		return False

def batch_convert():
	script_dir = Path(__file__).parent
	plist_files = list(script_dir.glob('level*_data.plist'))
	
	if not plist_files:
		print("未找到levelXX_data.plist文件")
		return
	
	for plist_file in plist_files:
		result = convert_plist_to_lua(plist_file)

if __name__ == "__main__":
	batch_convert()