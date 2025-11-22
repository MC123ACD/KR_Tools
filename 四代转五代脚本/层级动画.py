import plistlib
import os
import re
from collections import OrderedDict

def convert_plist_to_lua(plist_path, lua_path):
	"""将单个.plist文件转换为.lua文件"""
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f, dict_type=OrderedDict)
	
	animations = plist_data.get('animations', {})
	
	lua_table = {}
	for anim_name, anim_data in animations.items():
		# 使用正则表达式匹配xxx_action格式
		match = re.match(r'^([a-zA-Z0-9_]+)_([a-zA-Z0-9_]+)$', anim_name)
		if match:
			prefix = match.group(1)  # 获取xxx部分
			action = match.group(2)  # 获取action部分
			new_key = f"{prefix}_layerX_{action}"
		else:
			# 如果不匹配xxx_action格式，保持原样
			new_key = anim_name
		
		lua_table[new_key] = {
			"layer_to": anim_data["layerEnd"],
			"from": anim_data["fromIndex"],
			"layer_prefix": anim_data["prefix"] + "%i",
			"to": anim_data["toIndex"],
			"layer_from": anim_data["layerStart"]
		}
	
	with open(lua_path, 'w') as f:
		f.write("return {\n")
		for anim_name, anim_data in lua_table.items():
			f.write(f"    {anim_name} = {{\n")
			for key, value in anim_data.items():
				if isinstance(value, str):
					f.write(f'        {key} = "{value}",\n')
				else:
					f.write(f'        {key} = {value},\n')
			f.write("    },\n")
		f.write("}\n")

def batch_convert_plist_to_lua(folder_path):
	"""批量处理文件夹内所有.plist文件"""
	for filename in os.listdir(folder_path):
		if filename.endswith('.plist'):
			plist_path = os.path.join(folder_path, filename)
			lua_filename = filename.replace('.plist', '.lua')
			lua_path = os.path.join(folder_path, lua_filename)
			
			print(f"Converting {filename} -> {lua_filename}...")
			try:
				convert_plist_to_lua(plist_path, lua_path)
				print(f"Successfully converted: {lua_filename}")
			except Exception as e:
				print(f"Failed to convert {filename}: {str(e)}")

# 使用示例
if __name__ == "__main__":
	folder_path = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
	batch_convert_plist_to_lua(folder_path)