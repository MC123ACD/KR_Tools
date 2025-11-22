import plistlib
import re
import os
from pathlib import Path

def modify_terrain_type(plist_path, column=None, row=None, new_terrain_type=2):
	"""
	修改plist文件中指定行或列的terrainType值
	:param plist_path: plist文件路径
	:param column: 要修改的列(从0开始)，如果为None则修改行
	:param row: 要修改的行(从0开始)，如果为None则修改列
	:param new_terrain_type: 新的terrainType值
	"""
	try:
		with open(plist_path, 'rb') as f:
			plist_data = plistlib.load(f)
		
		if 'grid_pc' not in plist_data:
			print(f"{os.path.basename(plist_path)} 中没有找到 grid_pc 数据")
			return False
		
		modified = False
		for cell in plist_data['grid_pc']:
			# 将字符串值转换为整数比较
			cell_column = int(cell['column'])
			cell_row = int(cell['row'])
			
			# 检查是否匹配要修改的行或列
			if (column is not None and cell_column == column) or \
			   (row is not None and cell_row == row):
				cell['terrainType'] = str(new_terrain_type)
				modified = True
		
		if modified:
			with open(plist_path, 'wb') as f:
				plistlib.dump(plist_data, f)
			print(f"成功修改 {os.path.basename(plist_path)}")
			return True
		else:
			print(f"{os.path.basename(plist_path)} 中没有匹配的行或列")
			return False
	
	except Exception as e:
		print(f"处理 {os.path.basename(plist_path)} 时出错: {str(e)}")
		return False

def batch_modify_terrain(directory, column=None, row=None, new_terrain_type=2):
	"""
	批量修改目录下所有levelxx_data.plist文件
	:param directory: 包含plist文件的目录
	:param column: 要修改的列(从0开始)，如果为None则修改行
	:param row: 要修改的行(从0开始)，如果为None则修改列
	:param new_terrain_type: 新的terrainType值
	"""
	if column is None and row is None:
		print("必须指定要修改的列(column)或行(row)")
		return
	
	# 匹配 level<数字>_data.plist 的文件
	pattern = re.compile(r'level\d+_data\.plist$', re.IGNORECASE)
	
	# 获取所有匹配的plist文件
	plist_files = [f for f in Path(directory).glob('*') 
				  if f.is_file() and pattern.match(f.name)]
	
	if not plist_files:
		print(f"目录 {directory} 下未找到任何levelxx_data.plist文件")
		return
	
	success_count = 0
	for plist_file in plist_files:
		if modify_terrain_type(plist_file, column, row, new_terrain_type):
			success_count += 1
	
	print(f"\n处理完成: 共处理 {len(plist_files)} 个文件，成功修改 {success_count} 个")

if __name__ == "__main__":
	# 使用示例:
	# 修改当前目录下所有文件的第0列的terrainType为3
	batch_modify_terrain(
		directory='.',  # 当前目录
		column=None,       # 修改第0列
		row=35,       # 不指定行
		new_terrain_type=2  # 新的terrainType值
	)
	
	# 修改当前目录下所有文件的第5行的terrainType为1
	# batch_modify_terrain(
	#     directory='.',
	#     column=None,
	#     row=5,
	#     new_terrain_type=1
	# )