import os
import plistlib
from glob import glob
import re

def convert_plist_to_lua(plist_path):
	"""转换plist数据为Lua格式，同时生成paths、curves表和entities_list"""
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f)
	
	if 'paths_pc' not in plist_data:
		return None
	
	paths = []
	curves = []
	active_paths = []
	entities_list = []
	invalid_path_ranges = []
	
	# 遍历所有路径组
	for path_idx, path_group in enumerate(plist_data['paths_pc']):
		if 'subpaths' not in path_group:
			continue
		
		# 处理paths表（原始路径数据）
		path_nodes = []
		for subpath in path_group['subpaths']:
			if not subpath:
				continue
			points = [{'x': float(p['x']), 'y': float(p['y'])} for p in subpath]
			path_nodes.append(points)
		
		if path_nodes:
			paths.append(path_nodes)
			active_paths.append(True)
		
		# 处理curves表（采样数据）
		for subpath in path_group['subpaths'][:1]:  # 每个路径组只取第一个子路径生成curve
			if not subpath:
				continue
				
			# 采样逻辑：首点 + 每隔8点 + 末点
			sampled_nodes = []
			sample_interval = 8
			total_points = len(subpath)
			
			# 添加首点
			sampled_nodes.append({
				'x': float(subpath[0]['x']),
				'y': float(subpath[0]['y'])
			})
			
			# 每隔8个点采样
			for i in range(sample_interval, total_points, sample_interval):
				sampled_nodes.append({
					'x': float(subpath[i]['x']),
					'y': float(subpath[i]['y'])
				})
			
			# 添加末点（如果未被采样）
			if (total_points - 1) % sample_interval != 0:
				last_point = {
					'x': float(subpath[-1]['x']),
					'y': float(subpath[-1]['y'])
				}
				if not sampled_nodes or sampled_nodes[-1] != last_point:
					sampled_nodes.append(last_point)
			
			# 计算widths长度
			widths_length = (len(sampled_nodes) - 1) // 3 + 1
			widths = [40] * widths_length
			
			curves.append({
				'nodes': sampled_nodes,
				'widths': widths
			})
		
		# 检查是否有change_node信息
		if 'metadata' in path_group and 'segments' in path_group['metadata']:
			for segment in path_group['metadata']['segments']:
				if 'modifier' in segment:
					for modifier in segment['modifier']:
						if modifier.get('key') == 'change_node':
							# 创建entity条目
							entity = {
								'template': 'controller_teleport_enemies',
								'path': path_idx + 1,  # Lua索引从1开始
								'start_ni': int(modifier['from']) + 1,
								'end_ni': int(modifier['to']) + 1,
								'duration': float(modifier['duration'])
							}
							entities_list.append(entity)
							
							# 创建invalid_path_ranges条目
							invalid_range = {
								'from': int(modifier['from']) + 1,
								'to': int(modifier['to']) + 1,
								'path_id': path_idx + 1
							}
							invalid_path_ranges.append(invalid_range)
	
	return {
		'entities_list': entities_list,
		'invalid_path_ranges': invalid_path_ranges,
		'active': active_paths,
		'connections': [],
		'paths': paths,
		'curves': curves
	}

def generate_lua_file(data, output_path):
	"""生成Lua文件，entities_list表放在最前面"""
	with open(output_path, 'w', encoding='utf-8') as f:
		f.write("return {\n")
		
		# 1. 首先输出entities_list表
		if data['entities_list']:
			f.write("\tentities_list = {\n")
			for entity in data['entities_list']:
				f.write("\t\t{\n")
				for key, value in entity.items():
					if isinstance(value, str):
						f.write(f"\t\t\t{key} = \"{value}\",\n")
					else:
						f.write(f"\t\t\t{key} = {value},\n")
				f.write("\t\t},\n")
			f.write("\t},\n")
		
		# 2. 输出invalid_path_ranges表
		if data['invalid_path_ranges']:
			f.write("\tinvalid_path_ranges = {\n")
			for invalid_range in data['invalid_path_ranges']:
				f.write("\t\t{\n")
				f.write(f"\t\t\tfrom = {invalid_range['from']},\n")
				f.write(f"\t\t\tto = {invalid_range['to']},\n")
				f.write(f"\t\t\tpath_id = {invalid_range['path_id']},\n")
				f.write("\t\t},\n")
			f.write("\t},\n")
		
		# 3. active表
		f.write("\tactive = {\n")
		for active in data['active']:
			f.write(f"\t\t{str(active).lower()},\n")
		f.write("\t},\n")
		
		# 4. connections表（空）
		f.write("\tconnections = {},\n")
		
		# 5. paths表（原始路径数据）
		f.write("\tpaths = {\n")
		for path in data['paths']:
			f.write("\t\t{\n")
			for subpath in path:
				f.write("\t\t\t{\n")
				for point in subpath:
					f.write(f"\t\t\t\t{{\n\t\t\t\t\tx = {point['x']},\n\t\t\t\t\ty = {point['y']}\n\t\t\t\t}},\n")
				f.write("\t\t\t},\n")
			f.write("\t\t},\n")
		f.write("\t},\n")
		
		# 6. curves表（采样数据）
		f.write("\tcurves = {\n")
		for curve in data['curves']:
			f.write("\t\t{\n")
			
			# 写入nodes
			f.write("\t\t\tnodes = {\n")
			for node in curve['nodes']:
				f.write(f"\t\t\t\t{{\n\t\t\t\t\tx = {node['x']},\n\t\t\t\t\ty = {node['y']}\n\t\t\t\t}},\n")
			f.write("\t\t\t},\n")
			
			# 写入widths
			f.write("\t\t\twidths = {\n\t\t\t\t")
			f.write(", ".join(map(str, curve['widths'])))
			f.write("\n\t\t\t}\n")
			
			f.write("\t\t},\n")
		f.write("\t}\n")
		
		f.write("}\n")

def process_folder(folder_path):
	# 匹配levelXX_data.plist格式的文件名
	pattern = re.compile(r'level\d+_data\.plist$', re.IGNORECASE)
	
	for filename in os.listdir(folder_path):
		if pattern.match(filename):
			plist_file = os.path.join(folder_path, filename)
			converted_data = convert_plist_to_lua(plist_file)
			if converted_data:
				# 生成level4xx_paths.lua格式的输出文件名
				base_name = re.sub(r'_data\.plist$', '', filename, flags=re.IGNORECASE)
				# 提取数字部分并在前面添加4
				match = re.match(r'level(\d+)', base_name)
				if match:
					level_num = match.group(1)
					output_file = os.path.join(folder_path, f"level4{level_num}_paths.lua")
				
				generate_lua_file(converted_data, output_file)
				print(f"转换完成: {filename} → {os.path.basename(output_file)}")

if __name__ == '__main__':
	# 获取当前脚本所在目录
	folder_path = os.path.dirname(os.path.abspath(__file__))
	process_folder(folder_path)