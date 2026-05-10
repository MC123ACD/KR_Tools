from tools import (
    decompiler,
    generate_waves,
    process_images,
    sort_table,
    split_atlas,
    generate_atlas,
    measure_anchor,
    plist_level_to_lua,
    plist_animation_to_lua,
    drag_rename,
)

tool_datas = {
    "decompiler": {
        "name": "反编译",
        "module": decompiler,
        "has_gui": True,
        "help": "用途：使用 luajit-decompiler 反编译 LuaJIT 字节码\n\n使用方法：\n1. 点击“浏览…”选择包含 LuaJIT 字节码文件的文件夹\n2. 点击“开始反编译”\n\n输入：选择的文件夹\n输出：output 目录（按反编译器规则生成对应的 .lua 文件）\n注意：需要 bin/luajit-decompiler-v2.exe 可用",
    },
    "generate_waves": {
        "name": "生成波次",
        "module": generate_waves,
        "has_gui": True,
        "help": "用途：编辑/生成关卡波次（waves）与出怪组（spawns）数据\n\n使用方法：\n1. 点击“从Lua文件加载配置”选择要编辑的波次 .lua 文件\n2. 在界面中选择波次/出怪组/怪物并修改参数\n3. 点击“保存为Lua文件”导出\n\n输入：一个现有的波次 .lua 文件（可在任意位置选择）\n输出：output 目录下生成/覆盖同名 .lua 文件\n提示：可在“全局设置”中调整帧转秒、斗蛐蛐等相关参数",
    },
    "process_images": {
        "name": "处理图像",
        "module": process_images,
        "has_gui": True,
        "help": "用途：批量处理图片（裁剪透明边、缩放、锐化、亮度、镜像、合并等）\n\n使用方法：\n1. 将要处理的图片或文件夹放入 input 目录\n2. 打开工具后按需勾选/调整处理选项与输出设置\n3. 点击“开始处理”\n\n输入：input 目录内的图片/子目录\n输出：output 目录（按工具设置写入处理后的图片）",
    },
    "sort_table": {
        "name": "排序表",
        "module": sort_table,
        "has_gui": False,
        "help": "用途：对 Lua 表（table）文件进行排序（字符串键按字母序、数字键按值排序）\n\n使用方法：\n1. 将需要处理的 .lua 文件放入 input 目录\n2. 点击“排序表”\n\n输入：input 目录内的 .lua 文件\n输出：output 目录下同名 .lua 文件",
    },
    "split_atlas": {
        "name": "拆分图集",
        "module": split_atlas,
        "has_gui": False,
        "help": "用途：将图集拆分为单张 PNG（根据 plist/lua 描述裁剪并恢复精灵位置）\n\n使用方法：\n1. 将 .plist（或图集 .lua 数据）与对应的图集图片（如 .png）放入 input 目录\n2. 点击“拆分图集”\n\n输入：input 目录内的 .plist/.lua 与对应图集图片\n输出：output/<图集名>/ 目录下的逐张 .png\n提示：是否删除临时 plist 可在“全局设置”中配置",
    },
    "generate_atlas": {
        "name": "合并图集",
        "module": generate_atlas,
        "has_gui": True,
        "help": "用途：将小图批量打包生成图集，并导出对应的 Lua 描述\n\n使用方法：\n1. 在 input 目录下创建若干子文件夹，每个子文件夹代表一个图集\n2. 将要合并的小图放入对应子文件夹\n3. 打开工具后配置输出格式/边框/间距/最大尺寸等参数\n4. 点击“开始生成”\n\n输入：input/<子文件夹>/ 内的图片\n输出：output 目录下的图集图片与同名 .lua 描述文件（格式与选项相关）",
    },
    "measure_anchor": {
        "name": "测量锚点",
        "module": measure_anchor,
        "has_gui": True,
        "help": "用途：对图片进行锚点、偏移、矩形等数据测量，并一键复制到剪贴板\n\n使用方法：\n1. 打开工具后选择一张图片加载\n2. 在画布上点击/拖动设置锚点、参考点或矩形（具体操作以界面提示为准）\n3. 使用右键菜单中的“复制图像大小/复制锚点坐标/复制偏移坐标/复制矩形偏移坐标”等功能\n\n输入：任意图片文件\n输出：无文件输出（结果复制到剪贴板，状态栏提示“已复制到剪贴板”）",
    },
    "plist_level_to_lua": {
        "name": "四代关卡数据转换",
        "module": plist_level_to_lua,
        "has_gui": False,
        "help": "用途：将四代关卡相关的 Plist 数据转换为 Lua\n\n使用方法：\n1. 将关卡相关的 Plist 文件（关卡的 data / waves / spawner 等）放入 input 目录\n2. 点击“四代关卡数据转换”\n\n输入：input 目录内的关卡 Plist 文件\n输出：output/levels、output/waves 等目录（按文件类型写入）\n提示：文件命名规则、补零位数等可在“全局设置”中配置",
    },
    "plist_animation_to_lua": {
        "name": "四代动画数据转换",
        "module": plist_animation_to_lua,
        "has_gui": False,
        "help": "用途：将动画相关 Plist 转换为 Lua（普通动画与骨骼动画）\n\n使用方法：\n1. 将文件名包含 animations / layer_animations 的 Plist 文件放入 input 目录\n2. 点击“四代动画数据转换”\n\n输入：input 目录内的动画 Plist 文件\n输出：output/animations 与 output/exoskeletons 目录下的 .lua 文件",
    },
    "drag_rename": {
        "name": "拖拽重命名",
        "module": drag_rename,
        "has_gui": True,
        "help": "用途：通过拖拽交换文件名，适合图片/资源批量对位重命名\n\n使用方法：\n1. 将需要重命名/对位的文件放入 input 目录\n2. 打开工具后会加载列表，可按名称/时间/大小排序与过滤\n3. 拖拽列表项到另一个项上进行交换\n4. 点击“撤销”或按 Ctrl+Z 撤销最近一次交换\n\n输入：input 目录内的文件\n输出：直接在 input 目录内完成重命名/交换（无额外导出）\n提示：可配置关联文件替换规则，用于同时处理相关联的文件",
    },
}

