import plistlib
import os
from collections import OrderedDict

def convert_plist_to_lua(plist_path, lua_path):
	"""将.plist文件转换为指定格式的.lua文件"""
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f, dict_type=OrderedDict)
	
	animations = plist_data.get('animations', {})
	
	lua_content = "return {\n"
	
	for anim_name, anim_data in animations.items():
		lua_content += f"\t{anim_name} = {{\n"
		lua_content += f"\t\tprefix = \"{anim_data['prefix']}\",\n"
		lua_content += f"\t\tto = {anim_data['toIndex']},\n"
		lua_content += f"\t\tfrom = {anim_data['fromIndex']}\n"
		lua_content += "\t},\n"
	
	lua_content += "}\n"
	
	with open(lua_path, 'w') as f:
		f.write(lua_content)

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

if __name__ == "__main__":
	folder_path = os.path.dirname(os.path.abspath(__file__))  # 当前脚本所在目录
	batch_convert_plist_to_lua(folder_path)