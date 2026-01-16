import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import traceback
from pathlib import Path
import lib.config as config
from lib.utils import run_app, run_decompiler
from lib.classes import WriteLua
from lib.constants import BASIC_FONT
from lib.templates import (
    write_waves_data_template,
    write_dove_spawns_criket_data_template,
)
import lib.log as log

# 设置日志记录
log = log.setup_logging(config.log_level, config.log_file)

DISABLED_MONSTER_KEY = set(["creep", "creep_aux"])


def get_value_with_setting(default, criket):
    if setting["dove_spawn_cricket"]:
        return criket

    return default


def check_frames_to_seconds():
    if setting["frames_to_seconds"] or check_cricket_open():
        return True

    return False


def check_cricket_open():
    if setting["dove_spawn_cricket"]:
        return True

    return False


def get_default_setting(key=None):
    default_cricket_data = setting["default_cricket_data"]

    if key:
        if check_cricket_open() and default_cricket_data.get(key):
            return default_cricket_data[key]

        return setting["default_wave_data"][key]

    if default_cricket_data:
        return default_cricket_data

    return setting["default_wave_data"]


def get_monsters_dict(get_id=False, get_all=False):
    """
    加载怪物映射数据

    Args:
        is_all: 是否加载所有怪物类型

    Returns:
        dict: 怪物映射字典，包含正向和反向映射
    """
    monsters = {}

    # 遍历配置中的怪物类型
    for key, value in config.setting["generate_waves"]["monsters"].items():
        # 检查是否启用该怪物类型
        if not get_all and not config.setting["generate_waves"].get("enabled_" + key):
            continue

        for k, v in value.items():
            if get_id:
                # 添加反向映射（名称 -> id）
                monsters[k] = v
            else:
                # 添加正向映射（id -> 名称）
                monsters[v] = k

    return monsters


MONSTERS_ID = get_monsters_dict(True)
MONSTERS_NAME = get_monsters_dict()


def get_monsters_id(monster_name):
    return MONSTERS_ID.get(monster_name, monster_name)


def get_monsters_name(monster_id):
    return MONSTERS_NAME.get(monster_id, monster_id)


class GeneratorWave:
    """
    波次生成器主类

    提供GUI界面用于创建和编辑游戏中的波次数据（出怪配置），
    支持两种模式：
    1. 普通波次模式（适用于常规关卡）
    2. 斗蛐蛐波次模式（特殊模式，简化界面）

    主要功能：
    - 创建和管理多个波次
    - 在每个波次中添加多个出怪组
    - 在每个出怪组中添加多个怪物生成配置
    - 支持加载和保存为Lua格式文件
    - 支持时间单位转换（帧到秒）
    """

    def __init__(self, root):
        """
        初始化波次生成器

        Args:
            root: Tkinter根窗口或Toplevel窗口
        """
        self.root = root
        self.root.title("波次生成")  # 窗口标题
        self.root.geometry("1100x750")  # 窗口初始大小

        # 初始化波次数据结构
        self.waves_data = {
            "cash": get_default_setting("cash"),  # 初始金币
            "groups": [],  # 波次列表
        }

        if check_cricket_open():
            self.waves_data["required_textures"] = setting["default_cricket_data"][
                "required_textures"
            ]

        # 当前状态变量
        self.current_wave_index = 0  # 当前选中的波次索引
        self.last_listbox_selected = ""  # 上次选中的出怪组索引
        # 根据配置确定要加载的Lua文件名
        self.load_luafile = get_value_with_setting("level01_waves_campaign", "cricket")

        # 创建UI组件
        self.create_widgets()

        # 添加初始波次
        self.add_wave()

        # 延迟设置焦点到金币输入框
        self.root.after(10, self.entry_focus, self.cash_entry)

    def get_groups(self):
        return self.waves_data["groups"]

    def get_current_wave(self, key=None):
        wave = self.waves_data["groups"][self.current_wave_index]

        if key:
            return wave[key]

        return wave

    def set_current_wave(self, new_wave):
        self.waves_data["groups"][self.current_wave_index] = new_wave

    def get_selected_spawns_idx(self):
        curselection = self.spawns_listbox.curselection()

        return curselection

    def get_selected_spawns(self):
        idx = self.spawns_listbox.curselection()[0]
        return self.get_current_wave("spawns")[idx]

    def get_selected_monster_id(self):
        selected_monster_id = self.monster_tree.selection()

        return selected_monster_id

    def get_selected_monster_idx(self):
        id = self.get_selected_monster_id()[0]

        return self.monster_tree.index(id)

    def get_selected_monster(self):
        idx = self.get_selected_monster_idx()
        spawns = self.get_selected_spawns()

        return spawns["spawns"][idx]

    def get_monster_data(self, monster):
        data_list = []

        for key, value in monster.items():
            if key in DISABLED_MONSTER_KEY:
                continue

            data_list.append(value)

        return data_list

    def create_widgets(self):
        """创建所有UI组件"""
        # 创建控制按钮区域
        self.create_control_buttons()

        # 如果不是斗蛐蛐模式，创建波次控制区域
        if not check_cricket_open():
            self.create_wave_control()

        # 创建初始资源设置区域
        self.create_initial_resource_frame()

        if not check_cricket_open():
            # 创建波次按钮区域（用于切换波次）
            self.create_wave_buttons_frame()

            # 创建波次参数设置区域
            self.create_wave_params_frame()

        # 创建主编辑区域（出怪组管理和出怪设置）
        self.create_edit_area()

        # 创建状态栏
        self.create_status_bar()

        # 如果不是斗蛐蛐模式，初始化波次按钮
        if not check_cricket_open():
            self.update_wave_buttons()

    def create_control_buttons(self):
        """创建控制按钮（保存、加载）"""
        set_frame = tk.Frame(self.root)
        set_frame.pack(fill="x", padx=10, pady=5)

        # 保存按钮 - 将当前配置保存为Lua文件
        self.save_btn = tk.Button(
            set_frame,
            text="保存为Lua文件",
            command=self.save_to_lua,
            bg="#27ae60",  # 绿色背景
            fg="white",  # 白色文字
            font=(BASIC_FONT, 10),
            relief=tk.RAISED,  # 凸起效果
            padx=15,  # 水平内边距
            pady=2,  # 垂直内边距
        )
        self.save_btn.pack(side="left", padx=5)

        # 添加工具提示（简化版）
        self.create_tooltip(self.save_btn, "将当前波次配置保存为Lua文件")

        # 加载按钮 - 从Lua文件加载配置
        self.load_btn = tk.Button(
            set_frame,
            text="加载Lua文件",
            command=self.load_from_lua,
            bg="#9b59b6",  # 紫色背景
            fg="white",
            font=(BASIC_FONT, 10),
            relief=tk.RAISED,
            padx=15,
            pady=2,
        )
        self.load_btn.pack(side="left", padx=5)

        self.create_tooltip(self.load_btn, "从Lua文件加载波次配置")

    def create_tooltip(self, widget, text):
        """
        创建简单的工具提示

        Args:
            widget: 要添加工具提示的控件
            text: 工具提示文本
        """

        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)  # 无边框窗口
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = tk.Label(
                tooltip, text=text, background="yellow", relief="solid", borderwidth=1
            )
            label.pack()

            widget.tooltip = tooltip

        def hide_tooltip(event):
            if hasattr(widget, "tooltip"):
                widget.tooltip.destroy()
                delattr(widget, "tooltip")

        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", hide_tooltip)

    def create_wave_control(self):
        """创建波次管理区域（添加/删除波次）"""
        control_frame = tk.LabelFrame(
            self.root,
            text="波次管理",
            font=(BASIC_FONT, 10, "bold"),
            bg="#f0f0f0",
            padx=10,
            pady=10,
            relief=tk.GROOVE,
            borderwidth=2,
        )
        control_frame.pack(fill="x", padx=10, pady=5)

        # 添加新波次按钮
        self.add_wave_btn = tk.Button(
            control_frame,
            text="添加新波次",
            command=self.add_wave,
            bg="#3498db",  # 蓝色背景
            fg="white",
            font=(BASIC_FONT, 10),
            relief=tk.RAISED,
            padx=15,
            pady=2,
        )
        self.add_wave_btn.pack(side="left", padx=5)

        self.create_tooltip(self.add_wave_btn, "添加一个新的波次")

        # 删除波次按钮
        self.delete_wave_btn = tk.Button(
            control_frame,
            text="删除波次",
            command=self.delete_wave,
            bg="#e74c3c",  # 红色背景
            fg="white",
            font=(BASIC_FONT, 10),
            relief=tk.RAISED,
            padx=15,
            pady=2,
        )
        self.delete_wave_btn.pack(side="left", padx=5)

        self.create_tooltip(self.delete_wave_btn, "删除当前选中的波次")

    def create_initial_resource_frame(self):
        """创建初始资源设置区域"""
        initial_resource_frame = tk.Frame(self.root, bg="#f0f0f0")
        initial_resource_frame.pack(fill="x", padx=10, pady=5)

        # 金币标签
        tk.Label(
            initial_resource_frame,
            text="初始金币:",
            bg="#f0f0f0",
            font=(BASIC_FONT, 10),
        ).pack(side="left", padx=5)

        # 金币输入框
        cash_value = get_default_setting("cash")
        self.cash_var = tk.IntVar(value=cash_value)

        self.cash_entry = ttk.Entry(
            initial_resource_frame,
            textvariable=self.cash_var,
            width=15,
            font=(BASIC_FONT, 10),
        )
        self.cash_entry.pack(side="left", padx=5)

        # 绑定回车事件，自动跳转到下一个输入框
        self.cash_entry.bind(
            "<Return>", lambda e, nw="spawn", i=0: self.on_enter(e, nw, i)
        )

        self.create_tooltip(self.cash_entry, "玩家在关卡开始时的初始金币数量")

    def create_wave_buttons_frame(self):
        """创建波次切换按钮区域"""
        self.wave_btn_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.wave_btn_frame.pack(fill="x", padx=10, pady=5)

    def create_wave_params_frame(self):
        """创建波次参数设置区域"""
        wave_param_frame = tk.Frame(self.root, bg="#f0f0f0")
        wave_param_frame.pack(fill="x", padx=10, pady=5)

        # 波次间隔标签（根据配置显示不同的文本）
        wave_interval_label_text = (
            "波次间隔(秒):" if check_frames_to_seconds() else "波次间隔:"
        )

        tk.Label(
            wave_param_frame,
            text=wave_interval_label_text,
            bg="#f0f0f0",
            font=(BASIC_FONT, 10),
        ).pack(side="left", padx=(20, 5))

        # 波次间隔输入框
        self.wave_interval_var = tk.IntVar(
            value=get_default_setting("waves")["wave_interval"]
        )

        self.wave_interval_entry = ttk.Entry(
            wave_param_frame,
            textvariable=self.wave_interval_var,
            width=15,
            font=(BASIC_FONT, 10),
        )
        self.wave_interval_entry.pack(side="left", padx=5)

        # 绑定回车事件
        self.wave_interval_entry.bind(
            "<Return>", lambda e, nw="spawn", i=1: self.on_enter(e, nw, i)
        )

        self.create_tooltip(self.wave_interval_entry, "当前波次开始的时间（秒或帧数）")

    def create_edit_area(self):
        """创建主编辑区域（包含出怪组管理和出怪设置）"""
        edit_frame = tk.Frame(self.root, bg="#f0f0f0")
        edit_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 配置编辑区域的网格权重
        edit_frame.columnconfigure(0, weight=1)
        edit_frame.columnconfigure(1, weight=3)
        edit_frame.rowconfigure(0, weight=1)

        # 创建左侧：出怪组管理区域
        self.create_wave_management(edit_frame)

        # 创建右侧：出怪设置区域
        self.create_spawn_setting(edit_frame)

    def create_wave_management(self, parent_frame):
        """
        创建出怪组管理区域

        Args:
            parent_frame: 父框架
        """
        # 出怪组管理框架
        group_frame = tk.LabelFrame(
            parent_frame,
            text="出怪组管理",
            font=(BASIC_FONT, 10, "bold"),
            bg="#f0f0f0",
            padx=10,
            pady=10,
            relief=tk.GROOVE,
            borderwidth=2,
        )
        group_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        group_frame.columnconfigure(0, weight=1)
        group_frame.rowconfigure(0, weight=1)
        group_frame.rowconfigure(1, weight=0)

        # 出怪组列表（Listbox）
        self.spawns_listbox = tk.Listbox(
            group_frame,
            width=25,
            height=15,
            font=(BASIC_FONT, 10),
            bg="white",
            bd=2,
            relief="groove",
            exportselection=False,  # 不在其他窗口共享选择
            selectbackground="#3498db",  # 选中背景色
            selectforeground="white",  # 选中文字颜色
        )
        self.spawns_listbox.pack(fill="both", expand=True, pady=(0, 10))

        # 绑定选择事件
        self.spawns_listbox.bind("<<ListboxSelect>>", self.on_spawns_select)

        # 出怪组操作按钮框架
        btn_frame = tk.Frame(group_frame, bg="#f0f0f0")
        btn_frame.pack(fill="x")

        # 添加出怪组按钮
        self.add_spawns_btn = tk.Button(
            btn_frame,
            text="添加出怪组",
            command=self.add_spawns,
            bg="#3498db",
            fg="white",
            font=(BASIC_FONT, 9),
            relief=tk.RAISED,
            padx=5,
            pady=3,
        )
        self.add_spawns_btn.pack(side="left", fill="x", expand=True, padx=2)

        self.create_tooltip(self.add_spawns_btn, "在当前波次中添加一个新的出怪组")

        # 移除出怪组按钮
        self.remove_group_btn = tk.Button(
            btn_frame,
            text="移除出怪组",
            command=self.remove_group,
            bg="#e74c3c",
            fg="white",
            font=(BASIC_FONT, 9),
            relief=tk.RAISED,
            padx=5,
            pady=3,
        )
        self.remove_group_btn.pack(side="left", fill="x", expand=True, padx=2)

        self.create_tooltip(self.remove_group_btn, "移除当前选中的出怪组")

    def create_spawn_setting(self, parent_frame):
        """
        创建出怪设置区域

        Args:
            parent_frame: 父框架
        """
        # 出怪设置框架
        spawn_frame = tk.LabelFrame(
            parent_frame,
            text="出怪设置",
            font=(BASIC_FONT, 10, "bold"),
            bg="#f0f0f0",
            padx=10,
            pady=10,
            relief=tk.GROOVE,
            borderwidth=2,
        )
        spawn_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        spawn_frame.columnconfigure(0, weight=1)
        spawn_frame.rowconfigure(0, weight=0)  # 参数区域
        spawn_frame.rowconfigure(1, weight=1)  # 怪物列表区域
        spawn_frame.rowconfigure(2, weight=0)  # 按钮区域

        # 出怪组参数设置区域
        self.create_spawn_params(spawn_frame)

        # 怪物列表显示区域
        self.create_monster_list(spawn_frame)

        # 怪物操作按钮区域
        self.create_monster_buttons(spawn_frame)

    def create_spawn_params(self, parent_frame):
        """
        创建出怪组参数设置区域

        Args:
            parent_frame: 父框架
        """
        param_frame = tk.Frame(parent_frame, bg="#f0f0f0")
        param_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        param_frame.columnconfigure(0, weight=0)  # 标签列
        param_frame.columnconfigure(1, weight=1)  # 输入框列
        param_frame.columnconfigure(2, weight=0)  # 标签列
        param_frame.columnconfigure(3, weight=1)  # 输入框列
        param_frame.columnconfigure(4, weight=0)  # 复选框列

        # 出怪组延迟设置
        delay_label_text = (
            "出怪组延迟(秒):" if setting["frames_to_seconds"] else "出怪组延迟:"
        )

        tk.Label(
            param_frame, text=delay_label_text, bg="#f0f0f0", font=(BASIC_FONT, 10)
        ).grid(row=0, column=0, sticky="e", padx=5, pady=5)

        # 延迟输入框
        self.delay_var = tk.IntVar()
        self.delay_entry = ttk.Entry(
            param_frame, textvariable=self.delay_var, width=15, font=(BASIC_FONT, 10)
        )
        self.delay_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # 绑定回车事件
        delay_i = get_value_with_setting(2, 1)
        self.delay_entry.bind(
            "<Return>",
            lambda e, nw="spawn", i=delay_i: self.on_enter(e, nw, i),
        )

        self.create_tooltip(self.delay_entry, "当前出怪组相对于波次开始的延迟时间")

        # 出怪路径设置
        tk.Label(
            param_frame, text="出怪路径:", bg="#f0f0f0", font=(BASIC_FONT, 10)
        ).grid(row=0, column=2, sticky="e", padx=5, pady=5)

        # 路径索引输入框
        self.path_index_var = tk.IntVar()
        self.path_index_entry = ttk.Entry(
            param_frame,
            textvariable=self.path_index_var,
            width=15,
            font=(BASIC_FONT, 10),
        )
        self.path_index_entry.grid(row=0, column=3, sticky="w", padx=5, pady=5)

        # 绑定回车事件
        path_i = get_value_with_setting(3, 2)
        self.path_index_entry.bind(
            "<Return>",
            lambda e, nw="spawn", i=path_i: self.on_enter(e, nw, i),
        )

        self.create_tooltip(self.path_index_entry, "怪物行走的路径索引")

        # 飞行怪物复选框
        self.is_flying_check_var = tk.BooleanVar(value=False)

        self.is_flying_check = ttk.Checkbutton(
            param_frame,
            text="是否有飞行怪物",
            variable=self.is_flying_check_var,
            command=self.on_checkbox_toggle,
            style="TCheckbutton",
        )
        self.is_flying_check.grid(
            row=0, column=4, columnspan=2, sticky=tk.W, pady=5, padx=10
        )

        self.create_tooltip(self.is_flying_check, "勾选表示本出怪组包含飞行怪物")

    def create_monster_list(self, parent_frame):
        """
        创建怪物列表显示区域（Treeview表格）

        Args:
            parent_frame: 父框架
        """
        monster_list_frame = tk.Frame(parent_frame, bg="#f0f0f0")
        monster_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        monster_list_frame.columnconfigure(0, weight=1)
        monster_list_frame.rowconfigure(0, weight=1)

        # 定义表格列
        columns = (
            "creep_name",  # 怪物类型
            "creep_aux_name",  # 交替怪物
            "max_same",  # 交替数量
            "max",  # 总数量
            "interval",  # 生成间隔
            "subpath",  # 是否随机子路径
            "interval_next",  # 下一批延迟
        )

        # 创建Treeview表格
        self.monster_tree = ttk.Treeview(
            monster_list_frame,
            columns=columns,
            show="headings",  # 只显示表头
            height=8,
            selectmode="browse",  # 单选模式
        )

        # 配置表格样式
        style = ttk.Style()
        style.configure("Treeview", rowheight=25, font=(BASIC_FONT, 10))
        style.configure("Treeview.Heading", font=(BASIC_FONT, 10, "bold"))

        # 设置列标题
        self.monster_tree.heading("creep_name", text="怪物")
        self.monster_tree.heading("creep_aux_name", text="交替怪物")
        self.monster_tree.heading("max_same", text="交替数量")
        self.monster_tree.heading("max", text="总数量")

        # 根据配置显示不同的间隔标题
        interval_text = "间隔(秒)" if check_frames_to_seconds() else "间隔"
        self.monster_tree.heading("interval", text=interval_text)

        self.monster_tree.heading("subpath", text="子路径")

        # 根据配置显示不同的延迟标题
        interval_next_text = (
            "下一批间隔(秒)" if check_frames_to_seconds() else "下一批间隔"
        )
        self.monster_tree.heading("interval_next", text=interval_next_text)

        # 设置列宽和对齐方式
        self.monster_tree.column("creep_name", width=120, anchor="center", minwidth=80)
        self.monster_tree.column(
            "creep_aux_name", width=120, anchor="center", minwidth=80
        )
        self.monster_tree.column("max_same", width=80, anchor="center", minwidth=60)
        self.monster_tree.column("max", width=80, anchor="center", minwidth=60)
        self.monster_tree.column("interval", width=80, anchor="center", minwidth=60)
        self.monster_tree.column("subpath", width=100, anchor="center", minwidth=80)
        self.monster_tree.column(
            "interval_next", width=120, anchor="center", minwidth=80
        )

        # 将表格放置到框架中
        self.monster_tree.grid(row=0, column=0, sticky="nsew")

        # 添加垂直滚动条
        scrollbar = ttk.Scrollbar(
            monster_list_frame, orient="vertical", command=self.monster_tree.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.monster_tree.configure(yscrollcommand=scrollbar.set)

        # 绑定双击事件用于编辑怪物
        self.monster_tree.bind("<Double-1>", lambda e: self.edit_monster())

    def create_monster_buttons(self, parent_frame):
        """
        创建怪物操作按钮区域

        Args:
            parent_frame: 父框架
        """
        monster_btn_frame = tk.Frame(parent_frame, bg="#f0f0f0")
        monster_btn_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        # 配置按钮框架的网格权重
        for i in range(3):
            monster_btn_frame.columnconfigure(i, weight=1)

        # 添加怪物按钮
        self.add_monster_btn = tk.Button(
            monster_btn_frame,
            text="添加怪物",
            command=self.add_monster,
            bg="#3498db",
            fg="white",
            font=(BASIC_FONT, 9),
            relief=tk.RAISED,
            padx=10,
            pady=2,
        )
        self.add_monster_btn.grid(row=0, column=0, padx=2, pady=5, sticky="ew")

        self.create_tooltip(self.add_monster_btn, "在当前出怪组中添加一个新的怪物配置")

        # 编辑怪物按钮
        self.edit_monster_btn = tk.Button(
            monster_btn_frame,
            text="编辑怪物",
            command=self.edit_monster,
            bg="#f39c12",  # 橙色背景
            fg="white",
            font=(BASIC_FONT, 9),
            relief=tk.RAISED,
            padx=10,
            pady=2,
        )
        self.edit_monster_btn.grid(row=0, column=1, padx=2, pady=5, sticky="ew")

        self.create_tooltip(self.edit_monster_btn, "编辑当前选中的怪物配置")

        # 移除怪物按钮
        self.remove_monster_btn = tk.Button(
            monster_btn_frame,
            text="移除怪物",
            command=self.remove_monster,
            bg="#e74c3c",
            fg="white",
            font=(BASIC_FONT, 9),
            relief=tk.RAISED,
            padx=10,
            pady=2,
        )
        self.remove_monster_btn.grid(row=0, column=2, padx=2, pady=5, sticky="ew")

        self.create_tooltip(self.remove_monster_btn, "移除当前选中的怪物配置")

    def create_status_bar(self):
        """创建状态栏"""
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            bd=1,
            relief="sunken",  # 凹陷效果
            anchor="w",  # 左对齐
            bg="#f0f0f0",  # 背景色
            fg="#333333",  # 文字颜色
            font=(BASIC_FONT, 9),
            padx=10,  # 水平内边距
        )
        status_bar.pack(side="bottom", fill="x", padx=10, pady=5)

    def on_checkbox_toggle(self):
        """当飞行怪物复选框状态变化时调用"""
        selected = self.get_selected_spawns_idx()
        if not selected:
            return

        # 获取当前选中的出怪组
        selected_index = selected[0]
        group = self.get_current_wave("spawns")[selected_index]

        # 更新出怪组的飞行怪物标志
        if self.is_flying_check_var.get():
            group["some_flying"] = True
        else:
            group["some_flying"] = False

        # 更新状态栏
        self.status_var.set(
            f"已{'启用' if group['some_flying'] else '禁用'}飞行怪物标志"
        )

    def update_wave_buttons(self):
        """更新波次切换按钮"""
        # 清除现有的波次按钮
        for widget in self.wave_btn_frame.winfo_children():
            widget.destroy()

        # 为每个波次创建按钮
        for i in range(len(self.get_groups())):
            btn = tk.Button(
                self.wave_btn_frame,
                text=f"第{i+1}波",
                command=lambda idx=i: self.select_wave(idx),
                bg=(
                    "#9b59b6" if i == self.current_wave_index else "#ecf0f1"
                ),  # 选中状态颜色
                fg="white" if i == self.current_wave_index else "black",
                font=(BASIC_FONT, 10, "bold"),
                relief=tk.RAISED,
                padx=15,
                pady=2,
            )
            btn.pack(side="left", padx=5, pady=5)

            self.create_tooltip(btn, f"切换到第{i+1}波次进行编辑")

    def add_wave(self):
        """添加一个新波次"""
        if not check_cricket_open():
            # 保存当前状态
            self.last_listbox_selected = ""
            self.save_initial_resource()
            self.save_wave(set_origin=False)

        # 创建新的波次数据结构
        new_wave = {
            "wave_interval": get_default_setting("waves")["wave_interval"],
            "spawns": [],
        }

        groups = self.get_groups()

        # 添加到波次列表
        groups.append(new_wave)
        self.current_wave_index = len(groups) - 1

        if not check_cricket_open():
            # 更新UI
            self.wave_interval_var.set(self.get_current_wave("wave_interval"))
            self.update_wave_buttons()
            self.clear_spawns_list()

            # 设置焦点到波次到来时间输入框
            self.root.after(3, self.entry_focus, self.wave_interval_entry)

        # 自动添加一个出怪组到新波次
        self.add_spawns()

        # 更新状态栏
        self.status_var.set(f"已添加第{self.current_wave_index+1}波")

        log.info(f"添加第{self.current_wave_index+1}波次")

    def delete_wave(self):
        """删除当前波次"""
        groups = self.get_groups()

        if len(groups) <= 1:
            messagebox.showwarning("警告", "至少需要保留一个波次")
            return

        if len(groups):
            # 保存当前状态
            self.last_listbox_selected = ""
            self.save_initial_resource()

            # 删除当前波次
            del groups[self.current_wave_index]
            self.current_wave_index = max(0, self.current_wave_index - 1)

            # 更新UI
            self.update_wave_buttons()
            self.load_current_wave()

            # 恢复选择
            if self.spawns_listbox.size() > 0:
                self.spawns_listbox.selection_clear(0, tk.END)
                self.spawns_listbox.selection_set(0)
                self.on_spawns_select()

            # 设置焦点
            if not check_cricket_open():
                self.entry_focus(self.wave_interval_entry)

            # 更新状态栏
            self.status_var.set(f"已删除第{self.current_wave_index+1}波")

            log.info(f"删除波次，当前为第{self.current_wave_index+1}波")

    def select_wave(self, index):
        """选择指定索引的波次"""
        if index < 0 or index >= len(self.get_groups()):
            return

        # 保存当前状态
        self.last_listbox_selected = ""
        self.save_wave(set_origin=False)
        self.save_initial_resource()

        # 切换到新波次
        self.current_wave_index = index
        if not check_cricket_open():
            self.wave_interval_var.set(self.get_current_wave("wave_interval"))

        # 更新UI
        self.update_wave_buttons()
        self.load_current_wave()

        # 恢复选择
        if self.spawns_listbox.size() > 0:
            self.spawns_listbox.selection_clear(0, tk.END)
            self.spawns_listbox.selection_set(0)
            self.on_spawns_select()

        # 设置焦点
        self.entry_focus(self.delay_entry)

        # 更新状态栏
        self.status_var.set(f"已选择第{self.current_wave_index+1}波")

        log.info(f"切换到第{self.current_wave_index+1}波次")

    def load_current_wave(self):
        """加载当前波次的数据到UI"""
        if self.current_wave_index < 0 or self.current_wave_index >= len(
            self.get_groups()
        ):
            return

        wave = self.get_current_wave()

        # 加载出怪组列表
        self.spawns_listbox.delete(0, tk.END)
        for i, _ in enumerate(wave["spawns"]):
            self.spawns_listbox.insert(tk.END, f"出怪组 {i+1}")

        # 清空怪物列表
        self.clear_monster_tree()

    def clear_spawns_list(self):
        """清空出怪组列表"""
        self.spawns_listbox.delete(0, tk.END)
        self.clear_monster_tree()

    def clear_monster_tree(self):
        """清空怪物列表"""
        for item in self.monster_tree.get_children():
            self.monster_tree.delete(item)

    def add_spawns(self):
        """在当前波次中添加一个新的出怪组"""
        if self.current_wave_index < 0:
            messagebox.showwarning("警告", "请先选择或添加一个波次")
            return

        # 创建新的出怪组数据结构
        new_spawns = {
            "some_flying": get_default_setting("spawns")["some_flying"],
            "delay": (get_default_setting("spawns")["delay"]),
            "path_index": (get_default_setting("spawns")["path_index"]),
            "spawns": [],
        }

        spawns = self.get_current_wave("spawns")

        # 添加到当前波次
        spawns.append(new_spawns)
        selected_index = len(spawns) - 1

        # 更新UI
        self.spawns_listbox.insert(tk.END, f"出怪组 {selected_index+1}")
        self.spawns_listbox.selection_clear(0, tk.END)
        self.spawns_listbox.selection_set(selected_index)
        self.on_spawns_select()

        # 更新状态栏
        self.status_var.set(f"已添加出怪组 {selected_index+1}")

        log.info(f"在第{self.current_wave_index+1}波次中添加出怪组{selected_index+1}")

    def remove_group(self):
        """移除当前选中的出怪组"""
        self.last_listbox_selected = ""
        if self.current_wave_index < 0:
            return

        selected_index = self.get_selected_spawns_idx()

        if not selected_index:
            messagebox.showwarning("警告", "请先选择一个出怪组")
            return

        # 确认删除
        if not messagebox.askyesno("确认", f"确定要删除出怪组 {selected_index+1} 吗？"):
            return

        # 删除出怪组
        self.get_current_wave("spawns").pop(selected_index)
        self.spawns_listbox.delete(selected_index)
        self.clear_monster_tree()

        # 重新编号所有出怪组
        self.renumber_all_groups()

        # 更新UI状态
        self.status_var.set(f"已移除出怪组 {selected_index+1}")
        self.delay_var.set(setting["default_waves_data"]["spawns"]["delay"])
        self.path_index_var.set(setting["default_waves_data"]["spawns"]["path_index"])

        # 恢复选择
        if self.spawns_listbox.size() > 0:
            new_selection = min(selected_index, self.spawns_listbox.size() - 1)
            self.spawns_listbox.selection_clear(0, tk.END)
            self.spawns_listbox.selection_set(new_selection)
            self.on_spawns_select()

        log.info(f"移除第{self.current_wave_index+1}波次的出怪组{selected_index+1}")

    def renumber_all_groups(self):
        """重新编号所有出怪组显示名称"""
        self.spawns_listbox.delete(0, tk.END)
        for i in range(len(self.get_current_wave("spawns"))):
            self.spawns_listbox.insert(tk.END, f"出怪组 {i+1}")

    def on_spawns_select(self, event=None):
        """当出怪组选择变化时调用"""
        selected = self.get_selected_spawns_idx()
        if not selected:
            return

        # 保存当前出怪组数据
        self.save_wave()

        selected_index = selected[0]
        # 记录当前选择
        self.last_listbox_selected = selected_index

        # 获取选中的出怪组数据
        wave_group = self.get_current_wave("spawns")[selected_index]

        # 设置焦点到延迟输入框
        self.root.after(1, self.entry_focus, self.delay_entry)

        # 加载怪物数据到表格
        self.clear_monster_tree()
        for spawn in wave_group["spawns"]:
            # 提取怪物数据并显示
            m = self.get_monster_data(spawn)
            self.monster_tree.insert("", "end", values=(m))

    def add_monster(self):
        """添加怪物到当前出怪组"""
        if not self.get_selected_spawns_idx():
            messagebox.showwarning("警告", "请先选择一个出怪组")
            return

        # 创建添加怪物对话框
        self.add_monster_dialog()

    def edit_monster(self):
        """编辑当前选中的怪物"""
        selected_spawns = self.get_selected_spawns_idx()
        if not selected_spawns:
            messagebox.showwarning("警告", "请先选择一个出怪组")
            return

        selected_monster = self.get_selected_monster_id()
        if not selected_monster:
            messagebox.showwarning("警告", "请先选择一个怪物")
            return

        # 获取怪物数据
        spawn = self.get_selected_monster()

        # 创建编辑怪物对话框
        self.add_monster_dialog(selected_spawns[0], spawn, edit=True)

    def remove_monster(self):
        """移除当前选中的怪物"""
        selected = self.get_selected_spawns_idx()
        if not selected:
            return

        selected_monster = self.get_selected_monster_id()
        if not selected_monster:
            return

        # 确认删除
        if not messagebox.askyesno("确认", "确定要删除这个怪物吗？"):
            return

        # 删除怪物数据
        selected_index = selected[0]
        monster_index = self.monster_tree.index(selected_monster[0])

        wave_group = self.get_current_wave("spawns")[selected_index]
        wave_group["spawns"].pop(monster_index)

        # 从表格中移除
        self.monster_tree.delete(selected_monster[0])
        self.status_var.set(f"已移除怪物")

        log.info(
            f"移除第{self.current_wave_index+1}波次出怪组{selected_index+1}的第{monster_index+1}个怪物"
        )

    def add_monster_dialog(self, monster_index=None, spawn=None, edit=None):
        """
        创建添加/编辑怪物对话框

        Args:
            monster_index: 怪物索引（编辑时使用）
            spawn: 怪物数据（编辑时使用）
            edit: 是否为编辑模式
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(
            "添加怪物" if monster_index is None and edit != True else "编辑怪物"
        )
        dialog.geometry("500x500")  # 增大对话框尺寸
        dialog.transient(self.root)  # 设置为临时窗口
        dialog.grab_set()  # 模态对话框

        # 窗口居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # 创建主框架
        form_frame = tk.Frame(dialog, padx=15, pady=15)
        form_frame.pack(fill="both", expand=True)

        # 获取怪物列表
        monsters_keys = [k for k in get_monsters_dict(True)]
        if monsters_keys:
            monsters_keys.insert(0, "")  # 第一个选项为空

        # 怪物类型选择
        self.create_monster_form_field(
            form_frame, 0, "怪物:", monsters_keys, "creep_name", spawn, edit
        )

        # 交替怪物选择
        self.create_monster_form_field(
            form_frame, 1, "交替怪物:", monsters_keys, "creep_aux_name", spawn, edit
        )

        # 怪物参数设置
        self.create_monster_param_fields(form_frame, spawn)

        # 按钮区域
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)

        # 保存按钮
        save_text = "保存" if not edit else "更新"
        save_command = lambda: (
            (self.edit_update_monster(dialog) if edit else self.save_monster(dialog))
        )

        tk.Button(
            btn_frame,
            text=save_text,
            command=save_command,
            bg="#27ae60",
            fg="white",
            font=(BASIC_FONT, 10),
            padx=15,
            pady=2,
        ).pack(side="right", padx=5)

        # 取消按钮
        tk.Button(
            btn_frame,
            text="取消",
            command=dialog.destroy,
            font=(BASIC_FONT, 10),
            padx=15,
            pady=2,
        ).pack(side="right", padx=5)

        # 设置焦点
        self.entry_focus(self.max_same_entry)

        # 存储对话框引用
        self.dialog = dialog

    def create_monster_form_field(
        self, parent_frame, row, label_text, values, key, spawn=None, edit=None
    ):
        """
        创建怪物表单字段（下拉选择框）

        Args:
            parent_frame: 父框架
            row: 行号
            label_text: 标签文本
            values: 下拉框选项
            key: 数据键名
            spawn: 怪物数据（编辑时使用）
            edit: 是否为编辑模式
        """
        # 标签
        tk.Label(parent_frame, text=label_text, font=(BASIC_FONT, 10)).grid(
            row=row, column=0, sticky="e", padx=5, pady=8
        )

        # 下拉选择框
        var = tk.StringVar()
        combo = ttk.Combobox(
            parent_frame,
            textvariable=var,
            values=values,
            state="readonly",
            height=10,
            width=20,
            font=(BASIC_FONT, 10),
        )
        combo.grid(row=row, column=1, sticky="we", padx=5, pady=8, columnspan=2)

        # 填充现有数据（编辑模式）
        if spawn and edit:
            var.set(spawn.get(key, ""))

        # 存储变量引用
        setattr(self, f"{key}_var", var)
        setattr(self, f"{key}_combo", combo)

    def create_monster_param_fields(self, parent_frame, spawn=None):
        """
        创建怪物参数输入字段

        Args:
            parent_frame: 父框架
            spawn: 怪物数据（编辑时使用）
        """
        # 交替出怪数量
        self.create_param_field(
            parent_frame,
            2,
            "交替出怪数量:",
            "max_same",
            spawn,
            (get_default_setting("spawn")["max_same"]),
        )

        # 总出怪数量
        self.create_param_field(
            parent_frame,
            3,
            "总出怪数量:",
            "max",
            spawn,
            (get_default_setting("spawn")["max"]),
        )

        # 出怪间隔
        interval_label = "间隔(秒):" if check_frames_to_seconds() else "间隔:"
        self.create_param_field(
            parent_frame,
            4,
            interval_label,
            "interval",
            spawn,
            (get_default_setting("spawn")["interval"]),
        )

        # 出怪子路径
        self.create_param_field(
            parent_frame,
            5,
            "出怪子路径:",
            "subpath",
            spawn,
            (get_default_setting("spawn")["subpath"]),
        )

        # 下一出怪延迟
        interval_next_label = (
            "下一出怪延迟(秒):" if check_frames_to_seconds() else "下一出怪延迟:"
        )
        self.create_param_field(
            parent_frame,
            6,
            interval_next_label,
            "interval_next",
            spawn,
            (get_default_setting("spawn")["interval_next"]),
        )

    def create_param_field(
        self, parent_frame, row, label_text, key, spawn=None, default_value=""
    ):
        """
        创建参数输入字段

        Args:
            parent_frame: 父框架
            row: 行号
            label_text: 标签文本
            key: 数据键名
            spawn: 怪物数据（编辑时使用）
            default_value: 默认值
        """
        # 标签
        tk.Label(parent_frame, text=label_text, font=(BASIC_FONT, 10)).grid(
            row=row, column=0, sticky="e", padx=5, pady=8
        )

        # 输入框
        var = tk.StringVar(
            value=spawn.get(key, default_value) if spawn else default_value
        )
        entry = ttk.Entry(
            parent_frame, textvariable=var, font=(BASIC_FONT, 10), width=20
        )
        entry.grid(row=row, column=1, sticky="we", padx=5, pady=8, columnspan=2)

        # 绑定回车事件
        entry.bind(
            "<Return>", lambda e, nw="monster", i=row - 2: self.on_enter(e, nw, i)
        )

        # 添加验证（仅允许数字输入）
        def validate_input(new_value):
            if new_value == "":
                return True
            try:
                if "." in new_value:
                    float(new_value)
                else:
                    int(new_value)
                return True
            except ValueError:
                return False

        vcmd = (parent_frame.register(validate_input), "%P")
        entry.config(validate="key", validatecommand=vcmd)

        # 存储变量引用
        setattr(self, f"{key}_var", var)
        setattr(self, f"{key}_entry", entry)

        # 添加工具提示
        tooltips = {
            "max_same": "每次交替出怪的数量",
            "max": "总共要出的怪物数量",
            "interval": "每个怪物生成的时间间隔",
            "subpath": "怪物行走的子路径（0表示使用随机路径）",
            "interval_next": "出完当前批次后，等待多久再出下一批",
        }
        if key in tooltips:
            self.create_tooltip(entry, tooltips[key])

    def save_monster(self, dialog=None):
        """保存新添加的怪物"""
        selected_index = self.get_selected_spawns_idx()
        if not selected_index:
            if dialog:
                dialog.destroy()
            return

        index = selected_index[0]

        spawns = self.get_current_wave("spawns")[index]

        # 获取表单数据
        new_spawn = self.load_monster_data()

        # 验证必填字段
        if not new_spawn["creep_name"]:
            messagebox.showwarning("警告", "请选择怪物类型")
            return

        # 添加新怪物
        spawns["spawns"].append(new_spawn)

        # 更新表格显示
        m = self.get_monster_data(new_spawn)
        self.monster_tree.insert("", "end", values=(m))
        self.status_var.set("已添加怪物")

        log.info(f"添加怪物: {new_spawn['creep_name']}")

        # 关闭对话框
        if dialog:
            dialog.destroy()

    # def copy_monster(self):
    #     """复制怪物"""
    #     selected = self.get_selected_spawns_idx()
    #     if not selected:
    #         return

    #     spawns_index = selected[0]

    #     wave_group = self.get_current_wave("spawns")[spawns_index]

    #     # 添加新怪物
    #     wave_group["spawns"].append(self.get_selected_spawns())

    #     # 更新表格显示
    #     m = self.get_monster_data(new_spawn)
    #     self.monster_tree.insert("", "end", values=(m))
    #     self.status_var.set("已复制怪物")

    #     log.info(f"复制怪物: {new_spawn['creep_name']}")

    def edit_update_monster(self, dialog=None):
        """更新编辑的怪物"""
        selected_monster = self.get_selected_monster_id()
        if not selected_monster:
            if dialog:
                dialog.destroy()
            return

        monster_index = self.get_selected_monster_idx()

        wave_group = self.get_current_wave("spawns")[monster_index]

        # 获取表单数据
        new_spawn = self.load_monster_data()

        # 验证必填字段
        if not new_spawn["creep_name"]:
            messagebox.showwarning("警告", "请选择怪物类型")
            return

        # 更新怪物数据
        wave_group["spawns"][monster_index] = new_spawn

        # 更新表格显示
        m = self.get_monster_data(new_spawn)
        self.monster_tree.item(
            self.monster_tree.get_children()[monster_index], values=(m)
        )
        self.status_var.set("已更新怪物")

        log.info(f"更新怪物: {new_spawn['creep_name']}")

        # 关闭对话框
        if dialog:
            dialog.destroy()

    def load_monster_data(self):
        """
        从表单加载怪物数据

        Returns:
            dict: 怪物数据字典
        """
        try:
            creep_combo_v = str(self.creep_name_combo.get())
            creep_aux_combo_v = str(self.creep_aux_name_combo.get())
            max_same_v = int(self.max_same_var.get() or 0)
            max_v = int(self.max_var.get() or 0)
            interval_v = int(self.interval_var.get() or 0)
            subpath_v = int(self.subpath_var.get() or 0)
            interval_next_v = int(self.interval_next_var.get() or 0)

            dictionary = {
                "creep_name": creep_combo_v,
                "creep": get_monsters_id(creep_combo_v),
                "creep_aux_name": creep_aux_combo_v,
                "creep_aux": get_monsters_id(creep_aux_combo_v),
                "max_same": max_same_v,
                "max": max_v,
                "interval": interval_v,
                "subpath": subpath_v,
                "interval_next": interval_next_v,
            }
            return dictionary
        except ValueError as e:
            messagebox.showerror("错误", f"数据格式错误: {str(e)}")
            raise

    def save_to_lua(self):
        """保存当前配置为Lua文件"""
        # 确定保存路径
        file_path = config.output_path / f"{self.load_luafile}.lua"

        # 保存当前数据
        self.save_initial_resource()
        if self.get_selected_spawns_idx():
            self.save_wave()

        if not file_path:
            return

        try:
            # 根据模式选择不同的保存方式
            if not check_cricket_open():
                write_common_spawns(self.waves_data, file_path)
            else:
                write_dove_spawns_criket(self.waves_data, file_path)

            # 显示成功消息
            self.status_var.set(f"文件已保存: {file_path.name}")
            messagebox.showinfo("成功", f"文件已保存到:\n{file_path}")

            log.info(f"保存波次配置到: {file_path}")

        except Exception as e:
            messagebox.showerror("错误", f"保存文件时出错:\n{str(e)}")
            log.error(f"保存文件失败: {traceback.print_exc()}")

    def load_from_lua(self):
        """从Lua文件加载配置"""
        # 选择文件
        file_path = Path(
            filedialog.askopenfilename(
                filetypes=[("Lua 文件", "*.lua"), ("所有文件", "*.*")],
                title="选择要加载的波次文件",
            )
        )

        if not file_path:
            return

        try:
            run_decompiler(file_path, file_path.parent)

            # 读取并执行Lua文件
            with open(file_path, "r", encoding="utf-8-sig") as f:
                lua_data = config.lupa.execute(f.read())

            # 重置当前数据
            self.waves_data["cash"] = lua_data["cash"]

            # 根据模式加载数据
            if not check_cricket_open():
                load_common_spawns(self.waves_data, lua_data)
            else:
                dove_spawns_criket(self.waves_data, lua_data)

            # 更新UI状态
            self.current_wave_index = 0
            self.cash_var.set(lua_data["cash"])

            if not check_cricket_open():
                groups = self.get_groups()
                self.update_wave_buttons()
                if groups:
                    self.wave_interval_var.set(groups[0]["wave_interval"])

            # 加载数据到UI
            self.load_current_wave()
            if self.spawns_listbox.size() > 0:
                self.spawns_listbox.selection_clear(0, tk.END)
                self.spawns_listbox.selection_set(0)
                self.on_spawns_select()

            # 更新加载的文件名
            if not check_cricket_open():
                self.load_luafile = file_path.name.replace(".lua", "")

            # 显示成功消息
            self.status_var.set(f"已加载 {self.load_luafile} 文件")
            messagebox.showinfo("成功", f"已加载文件: {file_path.name}")

            log.info(f"从文件加载波次配置: {file_path}")

        except Exception as e:
            messagebox.showerror("错误", f"加载文件时出错:\n{str(e)}")
            log.error(f"加载文件失败: {file_path} - {traceback.print_exc()}")

    def save_initial_resource(self):
        """保存初始资源设置"""
        waves_data = self.waves_data
        group = waves_data["groups"]

        if group:
            wave = group[self.current_wave_index]

            # 保存金币
            try:
                waves_data["cash"] = int(self.cash_var.get())
            except ValueError:
                waves_data["cash"] = 0
                self.cash_var.set(0)

            # 保存波次间隔（非斗蛐蛐模式）
            if not check_cricket_open():
                try:
                    wave["wave_interval"] = self.wave_interval_var.get()
                except ValueError:
                    wave["wave_interval"] = 0
                    self.wave_interval_var.set(0)

    def save_wave(self, set_origin=True):
        """
        保存波次数据

        Args:
            set_origin: 是否从UI加载数据到数据结构
        """
        if self.get_groups():
            wave = self.get_current_wave()
            spawns = wave["spawns"]

            if spawns:
                # 保存上次选择的出怪组数据
                if set_origin and self.last_listbox_selected != "":
                    try:
                        last_spawns = spawns[self.last_listbox_selected]
                        last_spawns["delay"] = int(self.delay_var.get())
                        last_spawns["path_index"] = int(self.path_index_var.get())
                    except ValueError:
                        pass  # 保持原值

                selected_spawns = self.get_selected_spawns_idx()

                # 更新当前选择的出怪组
                if selected_spawns:
                    selected_spawn = self.get_selected_spawns()

                    if set_origin:
                        # 从数据结构更新UI
                        self.is_flying_check_var.set(selected_spawn["some_flying"])
                        self.delay_var.set(selected_spawn["delay"])
                        self.path_index_var.set(selected_spawn["path_index"])
                    else:
                        # 从UI更新数据结构
                        try:
                            selected_spawn["delay"] = int(self.delay_var.get())
                            selected_spawn["path_index"] = int(
                                self.path_index_var.get()
                            )
                        except ValueError:
                            pass  # 保持原值

                        # 清空UI（用于切换时）
                        self.delay_var.set("")
                        self.path_index_var.set("")

    def on_enter(self, event, next_widget, index):
        """
        回车键事件处理：聚焦下一个控件

        Args:
            event: 事件对象
            next_widget: 下一组控件类型（"spawn"或"monster"）
            index: 当前控件索引
        """
        widget_mapping = {}

        if next_widget == "spawn":
            # 出怪组参数控件顺序
            if not check_cricket_open():
                widget_mapping["spawn"] = [
                    self.cash_entry,
                    self.wave_interval_entry,
                    self.delay_entry,
                    self.path_index_entry,
                ]
            else:
                widget_mapping["spawn"] = [
                    self.cash_entry,
                    self.delay_entry,
                    self.path_index_entry,
                ]

            # 如果是最后一个控件，打开添加怪物对话框
            if index >= len(widget_mapping["spawn"]) - 1:
                self.add_monster()
                return "break"

        elif next_widget == "monster":
            # 怪物参数控件顺序
            widget_mapping["monster"] = [
                self.max_same_entry,
                self.max_entry,
                self.interval_entry,
                self.subpath_entry,
                self.interval_next_entry,
            ]

            # 如果是最后一个控件，保存怪物
            if index >= len(widget_mapping["monster"]) - 1:
                self.save_monster()
                return "break"

        # 聚焦下一个控件
        self.entry_focus(widget_mapping[next_widget][index + 1])

        return "break"  # 阻止默认回车行为

    def entry_focus(self, entry):
        """
        聚焦到指定输入框

        Args:
            entry: 要聚焦的输入框控件
        """
        entry.focus()
        self.select_all_text(entry)

    def select_all_text(self, entry):
        """
        全选输入框中的文本

        Args:
            entry: 输入框控件
        """
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)  # 将光标移到末尾


def load_monster_from_lua(spawn):
    creep = spawn["creep"]
    creep_aux = spawn["creep_aux"] or ""

    return {
        "creep": creep,
        "creep_name": get_monsters_name(creep),
        "creep_aux": creep_aux,
        "creep_aux_name": get_monsters_name(creep_aux),
        "max_same": spawn["max_same"] or 0,
        "max": spawn["max"],
        "interval": spawn["interval"],
        "subpath": spawn["path"] if spawn["fixed_sub_path"] else 0,
        "interval_next": spawn["interval_next"],
    }


def load_common_spawns(waves_data, lua_data):
    """
    加载普通波次模式的数据

    Args:
        data: 从Lua文件解析的数据
    """
    waves_data["groups"] = []

    # 遍历所有波次
    for wave in lua_data["groups"].values():
        new_wave_data = {
            "wave_interval": wave["interval"],
            "spawns": [],
        }

        # 时间单位转换
        if setting["frames_to_seconds"]:
            new_wave_data["wave_interval"] = round(
                new_wave_data["wave_interval"] / 30, 2
            )

        # 遍历出怪组
        for spawns in wave["waves"].values():
            new_spawns_data = {
                "some_flying": spawns["some_flying"] or False,
                "delay": spawns["delay"],
                "path_index": spawns["path_index"],
                "spawns": [],
            }

            # 时间单位转换
            if setting["frames_to_seconds"]:
                new_spawns_data["delay"] = round(new_spawns_data["delay"] / 30, 2)

            # 遍历怪物
            for spawn in spawns["spawns"].values():
                new_spawn_data = load_monster_from_lua(spawn)

                # 时间单位转换
                if setting["frames_to_seconds"]:
                    new_spawn_data["interval"] = round(
                        new_spawn_data["interval"] / 30, 2
                    )
                    new_spawn_data["interval_next"] = round(
                        new_spawn_data["interval_next"] / 30, 2
                    )

                new_spawns_data["spawns"].append(new_spawn_data)
            new_wave_data["spawns"].append(new_spawns_data)
        waves_data["groups"].append(new_wave_data)


def dove_spawns_criket(waves_data, lua_data):
    """
    加载斗蛐蛐波次模式的数据

    Args:
        data: 从Lua文件解析的数据
    """
    waves_data["groups"] = [{"wave_interval": 0, "spawns": []}]

    # 遍历出怪组
    for group in lua_data["groups"].values():
        new_group_data = {
            "some_flying": group["some_flying"] or False,
            "delay": group["delay"],
            "path_index": group["path_index"],
            "spawns": [],
        }

        # 遍历怪物
        for spawn in group["spawns"].values():
            new_spawn_data = load_monster_from_lua(spawn)

            new_group_data["spawns"].append(new_spawn_data)

        waves_data["groups"][0]["waves"].append(new_group_data)


def write_common_spawns(waves_data, file_path):
    """
    写入普通波次模式的Lua文件

    Args:
        file_path: 文件路径
        monsters: 怪物映射数据
    """
    lua_content = write_waves_data_template.render(waves_data)

    # 写入文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(lua_content)


def write_dove_spawns_criket(waves_data, file_path):
    """
    写入斗蛐蛐波次模式的Lua文件

    Args:
        file_path: 文件路径
        monsters: 怪物映射数据
    """
    groups = waves_data["groups"][0]["waves"]

    lua_content = write_dove_spawns_criket_data_template.render(groups)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(lua_content)


def main(root=None):
    """
    主函数：启动波次生成器

    Args:
        root: 父窗口，如果为None则创建新窗口
    """
    # 获取波次生成的配置
    global setting
    setting = config.setting["generate_waves"]

    # 运行应用程序
    run_app(root, GeneratorWave)


if __name__ == "__main__":
    main()
