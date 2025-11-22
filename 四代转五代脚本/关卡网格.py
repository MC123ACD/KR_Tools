import plistlib
from collections import defaultdict
import os
import re

def convert_plist_to_lua_grid(plist_path, lua_path):
	"""将 plist 文件中的 grid_pc 数据转换为 lua 格式的 grid
	
	参数:
		plist_path (str): plist 文件路径
		lua_path (str): 输出的 lua 文件路径
	"""
	# 1. 读取 plist 文件
	with open(plist_path, 'rb') as f:
		plist_data = plistlib.load(f)
	
	# 2. 获取 grid_pc 数据
	grid_pc = plist_data['grid_pc']
	
	# 3. 计算最大列数和行数
	max_column = 0
	max_row = 0
	for cell in grid_pc:
		column = int(cell['column'])
		row = int(cell['row'])
		if column > max_column:
			max_column = column
		if row > max_row:
			max_row = row
	
	# 4. 按列分组存储单元格数据
	columns = defaultdict(list)  # 使用字典存储每列的数据
	for cell in grid_pc:
		column = int(cell['column'])
		row = int(cell['row'])
		terrain_type = int(cell['terrainType'])
		columns[column].append((row, terrain_type))
	
	# 5. 构建 lua 的 grid 结构
	grid = []
	# 获取所有列的最大行数（确保空列与其他列行数一致）
	max_rows_in_grid = max(len(cells) for cells in columns.values()) if columns else 0

	for column in range(max_column + 1):
		if column in columns:
			# 对该列的数据排序（按行号降序）
			cells = sorted(columns[column], key=lambda x: x[0], reverse=True)
			# 转换地形类型：2→257，其他→1
			column_data = [257 if terrain == 2 else 1 for (row, terrain) in cells]
		else:
			# 空列：生成 max_rows_in_grid 个 1
			column_data = [1] * max_rows_in_grid
		
		grid.append(column_data)
	
	# 6. 生成 lua 文件内容
	lua_content = f"""return {{
	ox = -170.5,      -- 原点 x 坐标
	oy = -48,         -- 原点 y 坐标
	cell_size = 17.0625,  -- 单元格大小
	grid = {{          -- 网格数据
"""
	
	# 添加每列数据
	for column in grid:
		lua_content += "\t\t{\n\t\t\t"
		lua_content += ",\n\t\t\t".join(map(str, column))  # 将数字用逗号分隔
		lua_content += "\n\t\t},\n"
	
	lua_content += "\t}\n}"
	
	# 7. 写入 lua 文件
	with open(lua_path, 'w', encoding='utf-8') as f:
		f.write(lua_content)

def process_all_level_files():
	"""处理当前目录下所有符合条件的 plist 文件"""
	# 匹配 level开头+数字+_data.plist 的文件名模式
	pattern = re.compile(r'level(\d+)_data\.plist$')
	
	# 获取当前脚本所在目录
	script_dir = os.path.dirname(os.path.abspath(__file__))
	
	# 遍历目录下所有文件
	for filename in os.listdir(script_dir):
		match = pattern.match(filename)
		if match:
			# 提取关卡数字部分并在前面加4
			original_num = match.group(1)
			new_num = f'4{original_num}'  # 在原数字前加4
			plist_path = os.path.join(script_dir, filename)
			lua_filename = f'level{new_num}_grid.lua'  # 生成level4xx_grid.lua格式
			lua_path = os.path.join(script_dir, lua_filename)
			
			try:
				convert_plist_to_lua_grid(plist_path, lua_path)
				print(f'处理成功: {filename} -> {lua_filename}')
			except Exception as e:
				print(f'处理 {filename} 时出错: {str(e)}')

if __name__ == '__main__':
	process_all_level_files()