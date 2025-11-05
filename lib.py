from lupa.luajit20 import LuaRuntime
import traceback
from pathlib import Path


def find_and_create_directory(caller_file: str) -> tuple[str, str, str]:
    """
    查找与创建输入与输出目录
    """

    base_dir = Path(caller_file).parent
    input_path = base_dir / "input"
    output_path = base_dir / "output"

    if not input_path.exists():
        input_path.mkdir()
        input("💬 输入目录 input 不存在, 已自动创建, 按回车继续 >")

    if not output_path.exists():
        output_path.mkdir()

    while len(list(input_path.iterdir())) == 0:
        input("❌ 错误, 输入目录为空, 请放入Lua模块后按回车重试 >")

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
