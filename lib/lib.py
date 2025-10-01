import lupa.luajit20
from lupa import LuaRuntime
import re, os, traceback


def find_and_create_directory(caller_file: str) -> tuple[str, str, str]:
    """
    查找与创建输入与输出目录
    """

    base_dir = os.path.dirname(os.path.abspath(caller_file))
    input_path = os.path.join(base_dir, "input")
    output_path = os.path.join(base_dir, "output")

    if not os.path.exists(input_path):
        os.makedirs(input_path)
        input("💬 输入目录 input 不存在, 已自动创建, 按回车继续 >")

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    return base_dir, input_path, output_path


def init_lua(fn: str = None) -> object:
    """
    初始化Lua环境
    """

    try:
        lua = LuaRuntime(unpack_returned_tuples=True)

        if fn:
            lua.execute(fn)

        print("✅ Lua环境初始化完成")

        return lua
    except Exception as e:
        print(f"❌ Lua初始化失败: {str(e)}")
        return
