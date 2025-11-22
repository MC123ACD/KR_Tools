import plistlib
import sys
import os
from glob import glob

def convert_plist_to_lua(plist_path):
	base_name = os.path.basename(plist_path)
	parts = base_name.split('_')
	if len(parts) < 2:
		print(f"跳过文件 {base_name}：文件名格式不符合要求，应为levelXX_YYY.plist")
		return
	
	level_num = parts[0][5:]  # 从levelXX中提取XX
	mode_name = parts[1].split('.')[0]  # 从YYY.plist中提取YYY
	lua_filename = f"level4{level_num}_waves_{mode_name}.lua"
	
	try:
		# 读取plist文件
		with open(plist_path, 'rb') as f:
			plist_data = plistlib.load(f)
	except Exception as e:
		print(f"处理文件 {base_name} 时出错: {str(e)}")
		return
	
	# 准备lua数据结构
	lua_data = {
		'cash': plist_data.get('gold', 0),
		'groups': []
	}
	
	# 转换waves到groups
	for wave in plist_data.get('waves', []):
		group = {
			'interval': wave.get('interval', 0),
			'waves': []
		}
		
		for subwave in wave.get('subwaves', []):
			lua_wave = {
				'delay': subwave.get('interval', 0),
				'path_index': subwave.get('path_index', 0) + 1,
				'spawns': []
			}
			
			for spawn in subwave.get('spawns', []):
				fixed_sub_path = spawn.get('fixed_sub_path', -1)
				
				lua_spawn = {
					'interval': spawn.get('interval', 0),
					'creep': "enemy_" + spawn.get('enemy', ''),
					'max': spawn.get('cant', 0),
					'interval_next': spawn.get('interval_next_spawn', 0),
					'max_same': 0
				}
				
				if fixed_sub_path < 0:
					lua_spawn['fixed_sub_path'] = 0
					lua_spawn['path'] = 3
				else:
					lua_spawn['fixed_sub_path'] = 1
					lua_spawn['path'] = fixed_sub_path + 1
				
				lua_wave['spawns'].append(lua_spawn)
			
			group['waves'].append(lua_wave)
		
		lua_data['groups'].append(group)
	
	# 生成lua文件内容
	lua_content = "return {\n"
	lua_content += f"\tcash = {lua_data['cash']},\n"
	lua_content += "\tgroups = {\n"
	
	for group in lua_data['groups']:
		lua_content += "\t\t{\n"
		lua_content += f"\t\t\tinterval = {group['interval']},\n"
		lua_content += "\t\t\twaves = {\n"
		
		for wave in group['waves']:
			lua_content += "\t\t\t\t{\n"
			lua_content += f"\t\t\t\t\tdelay = {wave['delay']},\n"
			lua_content += f"\t\t\t\t\tpath_index = {wave['path_index']},\n"
			lua_content += "\t\t\t\t\tspawns = {\n"
			
			for spawn in wave['spawns']:
				lua_content += "\t\t\t\t\t\t{\n"
				lua_content += f"\t\t\t\t\t\t\tinterval = {spawn['interval']},\n"
				lua_content += f"\t\t\t\t\t\t\tmax_same = {spawn['max_same']},\n"
				lua_content += f"\t\t\t\t\t\t\tfixed_sub_path = {spawn['fixed_sub_path']},\n"
				lua_content += f"\t\t\t\t\t\t\tcreep = \"{spawn['creep']}\",\n"
				lua_content += f"\t\t\t\t\t\t\tpath = {spawn['path']},\n"
				lua_content += f"\t\t\t\t\t\t\tinterval_next = {spawn['interval_next']},\n"
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
	
	# 写入文件
	with open(lua_filename, 'w', encoding='utf-8') as f:
		f.write(lua_content)
	
	print(f"转换成功: {base_name} → {lua_filename}")

def batch_convert_plist_to_lua():
	# 获取脚本所在目录
	script_dir = os.path.dirname(os.path.abspath(__file__))
	
	# 查找所有plist文件
	plist_files = glob(os.path.join(script_dir, '*.plist'))
	
	if not plist_files:
		print("当前目录下未找到任何plist文件")
		return
	
	for plist_file in plist_files:
		convert_plist_to_lua(plist_file)
	
	print("所有文件处理完成")

if __name__ == "__main__":
	# 直接运行脚本时，自动处理当前目录下所有plist文件
	batch_convert_plist_to_lua()