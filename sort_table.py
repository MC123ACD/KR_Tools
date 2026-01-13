import traceback, config
from utils import is_simple_key, escape_lua_string
import log

log = log.setup_logging(config.log_level, config.log_file)


def process_table(file):
    lua_data = config.lupa.execute(file)

    string_keys = {}
    numeric_keys = []

    for key, value in lua_data.items():
        if isinstance(key, int):
            numeric_keys.append(value)
            continue

        string_keys[key] = value

    sorted_dict = {k: string_keys[k] for k in sorted(string_keys)}
    numeric_keys.sort()

    return sorted_dict, numeric_keys


def write_lua_file(lua_file_path: str, sorted_dict: dict, sorted_list: list):
    """
    写入lua文件
    """
    content = ["return {"]

    def a(str):
        content.append(str)

    a("return {\n")
    for k, v in sorted_dict.items():
        if is_simple_key(k):
            a(f'\t{escape_lua_string(k)} = "{escape_lua_string(v)}",')
        else:
            a(f'\t["{escape_lua_string(k)}"] = "{escape_lua_string(v)}",')
    for v in sorted_list:
        a(f'\t"{escape_lua_string(str(v))}",')
    a("}")

    log.info(f"✅ 处理完成！结果已保存到: {lua_file_path}")

    lua_content = "\n".join(content)

    with open(lua_file_path, "w", encoding="utf-8") as f:
        f.write(lua_content)


def main():
    for filename in config.input_path.iterdir():
        if filename.suffix != ".lua":
            log.warning(f"⚠️ 跳过无效文件{filename}")
            continue
        log.info(f"📖 读取文件: {filename}")

        # 读取Lua文件内容
        with open(filename, "r", encoding="utf-8-sig") as f:
            file = f.read()

        sorted_dict, sorted_list = process_table(file)

        write_lua_file(config.output_path / filename.name, sorted_dict, sorted_list)


if __name__ == "__main__":
    # 执行主函数并返回退出码
    success = main()
    exit(0 if success else 1)
