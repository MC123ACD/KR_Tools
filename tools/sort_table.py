import traceback
import lib.config as config
from lib.utils import run_decompiler
from lib.classes import WriteLua
import lib.log as log

# 初始化日志系统
log = log.setup_logging(config.log_level, config.log_file)


def process_table(file: str) -> tuple[dict, list]:
    """
    处理Lua表格内容，分离字符串键和数字键

    Args:
        file: Lua表格字符串内容

    Returns:
        tuple[dict, list]: 字符串键字典(已排序)和数字键列表(已排序)

    Raises:
        Exception: 当Lua解析或处理失败时抛出
    """
    try:
        # 执行Lua代码获取表格数据
        lua_data = config.lupa.execute(file)

        string_keys = {}
        numeric_keys = []

        # 遍历表格项，按键类型分类
        for key, value in lua_data.items():
            if isinstance(key, int):
                # 数字键存储到列表
                numeric_keys.append(value)
            else:
                # 字符串键存储到字典
                string_keys[key] = value

        # 对字符串键按字母顺序排序
        sorted_dict = {k: string_keys[k] for k in sorted(string_keys)}
        # 对数字键对应的值排序
        numeric_keys.sort()

        return sorted_dict, numeric_keys

    except Exception as e:
        log.error(f"处理Lua表格失败: {e}")
        log.debug(traceback.format_exc())
        raise


def gen_lua_content(sorted_dict, sorted_list):
    # 创建Lua写入器实例
    writer = WriteLua()
    # 获取格式化函数
    a, start, end, dict_v, list_v = writer.get_helpers()

    # 开始构建Lua表格
    a(0, "return {")

    # 写入字符串键值对（已排序）
    for key, value in sorted_dict.items():
        dict_v(1, key, value)

    # 写入数字键值列表（已排序）
    for value in sorted_list:
        list_v(1, value)

    # 结束表格
    end(0, False)

    return writer.get_content()


def write_lua_file(lua_file_path: str, sorted_dict: dict, sorted_list: list) -> bool:
    """
    将排序后的数据写入Lua文件

    Args:
        lua_file_path: 输出文件路径
        sorted_dict: 排序后的字符串键字典
        sorted_list: 排序后的数字键值列表

    Returns:
        bool: 写入是否成功

    Note:
        使用自定义WriteLua工具确保正确的Lua格式和缩进
    """
    try:
        # 获取生成的Lua内容
        lua_content = gen_lua_content(sorted_dict, sorted_list)

        # 写入文件
        with open(lua_file_path, "w", encoding="utf-8") as f:
            f.write(lua_content)

        log.info(f"✅ 处理完成！结果已保存到: {lua_file_path}")
        return True

    except Exception as e:
        log.error(f"写入Lua文件失败 {lua_file_path}: {e}")
        log.debug(traceback.format_exc())
        return False


def main() -> bool:
    """
    主处理函数：遍历输入目录处理所有Lua文件

    Returns:
        bool: 整体处理是否成功

    Workflow:
        1. 遍历config.input_path目录下的所有文件
        2. 过滤出.lua后缀的文件
        3. 对每个文件进行读取、处理、写入操作
        4. 记录处理结果并返回整体状态
    """
    success_count = 0
    total_count = 0

    # 遍历输入目录
    for filename in config.input_path.iterdir():
        # 跳过非Lua文件
        if filename.suffix != ".lua":
            log.debug(f"跳过非Lua文件: {filename}")
            continue

        run_decompiler(filename, config.input_path)

        total_count += 1
        log.info(f"📖 正在处理文件 ({total_count}): {filename}")

        try:
            # 读取Lua文件内容（使用utf-8-sig处理BOM）
            with open(filename, "r", encoding="utf-8-sig") as f:
                file = f.read()

            # 处理Lua表格
            sorted_dict, sorted_list = process_table(file)

            # 写入处理后的文件
            output_path = config.output_path / filename.name
            if write_lua_file(output_path, sorted_dict, sorted_list):
                success_count += 1

        except Exception as e:
            log.error(f"处理文件失败 {filename}: {e}")
            log.debug(traceback.format_exc())

    # 输出处理统计
    log.info(f"📊 处理完成统计: 成功 {success_count}/{total_count} 个文件")

    # 返回处理状态：全部成功为True，否则为False
    return success_count == total_count if total_count > 0 else True


if __name__ == "__main__":
    """
    程序入口点

    Exit Codes:
        0: 程序执行成功（所有文件处理成功）
        1: 程序执行失败（有文件处理失败）
    """
    # 执行主函数并获取状态
    success = main()

    # 根据处理状态返回退出码
    exit(0 if success else 1)
