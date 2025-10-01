import re, os, traceback, sys

# 添加上级目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from lib import lib

base_dir, input_path, output_path = lib.find_and_create_directory(__file__)
lua = lib.init_lua()


def sort_lua_table():
    """
    加载Lua模块，并排序返回的表
    """

    while len(os.listdir(input_path)) == 0:
        input("❌ 错误, 输入目录为空, 请放入Lua模块后按回车重试 >")

    for filename in os.listdir(input_path):
        if filename.endswith(".lua"):
            print(f"📖 读取文件: {filename}")

            try:
                # 读取Lua文件内容
                with open(
                    os.path.join(input_path, filename), "r", encoding="utf-8-sig"
                ) as f:
                    lua_module_return = lua.execute(f.read())

                    sorted_dict, list_table = process_table(lua_module_return)

                    write_lua_file(
                        os.path.join(output_path, filename), sorted_dict, list_table
                    )

            except Exception as e:
                print(f"❌ 处理错误 {filename}: {str(e)}")
                traceback.print_exc()
        else:
            print(f"⚠️ 跳过无效文件{filename}")
            return


def write_lua_file(lua_file_path: str, dict_table: dict, list_table: list):
    """
    写入lua文件
    """

    with open(lua_file_path, "w", encoding="utf-8") as f:
        f.write("return {\n")

        for k, v in dict_table.items():
            # 转义键和值
            escaped_key = escape_lua_string(str(k))
            escaped_value = escape_lua_string(str(v))
            f.write(f'\t["{escaped_key}"] = "{escaped_value}",\n')

        for v in list_table:
            # 转义列表值
            escaped_value = escape_lua_string(str(v))
            f.write(f'\t"{escaped_value}",\n')

        f.write("}")

    print(f"✅ 处理完成！结果已保存到: {lua_file_path}")


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


def process_table(table):
    """
    分离和排序键
    """
    string_keys = {}
    numeric_keys = []

    for i in range(1, len(table) + 1):
        if i in table:
            numeric_keys.append(value)

    for key, value in table.items():
        if not isinstance(key, int):
            string_keys[key] = value

    sorted_dict = {k: string_keys[k] for k in sorted(string_keys)}
    numeric_keys.sort()

    return sorted_dict, numeric_keys


if __name__ == "__main__":
    print("🚀 开始转换流程")
    print("=" * 50)

    sort_lua_table()

    input("程序执行完毕，按回车键退出...")
