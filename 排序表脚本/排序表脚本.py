import re, traceback, sys
from pathlib import Path


# 添加上级目录到Python路径，以便导入自定义库
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

import lib

base_dir, input_path, output_path = lib.find_and_create_directory(__file__)
lua = lib.init_lua()


def sort_lua_table():
    """
    加载Lua模块，并排序返回的表
    """
    for filename in input_path.iterdir():
        if filename.suffix == ".lua":
            print(f"📖 读取文件: {filename}")

            try:
                # 读取Lua文件内容
                with open(filename, "r", encoding="utf-8-sig") as f:
                    lua_module_return = lua.execute(f.read())

                    sorted_dict, sorted_list = process_table(lua_module_return)

                    write_lua_file(output_path / filename.name, sorted_dict, sorted_list)

            except Exception as e:
                print(f"❌ 处理错误 {filename}: {str(e)}")
                traceback.print_exc()
        else:
            print(f"⚠️ 跳过无效文件{filename}")
            return


def write_lua_file(lua_file_path: str, sorted_dict: dict, sorted_list: list):
    """
    写入lua文件
    """

    def escape_lua_string(s):
        """
        转义Lua字符串中的特殊字符
        """
        if not isinstance(s, str):
            return s

        # 转义特殊字符
        s = s.replace("\\", "\\\\")
        s = s.replace('"', '\\"')
        s = s.replace("\n", "\\n")
        s = s.replace("\r", "\\r")
        s = s.replace("\t", "\\t")
        return s

    def is_simple_key(key):
        """检查键名是否为简单标识符（只包含字母、数字、下划线，不以数字开头）"""
        if not key or key[0].isdigit():
            return False
        return all(c.isalnum() or c == "_" for c in key)

    with open(lua_file_path, "w", encoding="utf-8") as f:
        f.write("return {\n")

        for k, v in sorted_dict.items():
            if is_simple_key(k):
                f.write(f'\t{escape_lua_string(k)} = "{escape_lua_string(v)}",\n')
            else:
                f.write(f'\t["{escape_lua_string(k)}"] = "{escape_lua_string(v)}",\n')

        for v in sorted_list:
            f.write(f'\t"{escape_lua_string(str(v))}",\n')

        f.write("}")

    print(f"✅ 处理完成！结果已保存到: {lua_file_path}")


def process_table(table):
    """
    分离和排序键
    """
    string_keys = {}
    numeric_keys = []

    for key, value in table.items():
        if not isinstance(key, int):
            string_keys[key] = value
        elif isinstance(key, int):
            numeric_keys.append(value)

    sorted_dict = {k: string_keys[k] for k in sorted(string_keys)}
    numeric_keys.sort()

    return sorted_dict, numeric_keys


if __name__ == "__main__":
    print("🚀 开始转换流程")
    print("=" * 50)

    sort_lua_table()

    input("程序执行完毕，按回车键退出...")
