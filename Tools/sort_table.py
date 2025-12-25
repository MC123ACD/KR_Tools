import traceback, config
from utils import is_simple_key


def sort_lua_table():
    """
    加载Lua模块，并排序返回的表
    """
    for filename in config.input_path.iterdir():
        if filename.suffix == ".lua":
            print(f"📖 读取文件: {filename}")

            try:
                # 读取Lua文件内容
                with open(filename, "r", encoding="utf-8-sig") as f:
                    sorted_dict, sorted_list = process_table(f)

                    write_lua_file(
                        config.output_path / filename.name, sorted_dict, sorted_list
                    )

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


def process_table(f):
    lua_data = config.lupa.execute(f.read())

    string_keys = {}
    numeric_keys = []

    for key, value in lua_data.items():
        if not isinstance(key, int):
            string_keys[key] = value
        elif isinstance(key, int):
            numeric_keys.append(value)

    sorted_dict = {k: string_keys[k] for k in sorted(string_keys)}
    numeric_keys.sort()

    return sorted_dict, numeric_keys


def main():
    sort_lua_table()
