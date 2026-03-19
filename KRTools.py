import subprocess, json, traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import lib.log as log
import lib.config as config
from lib.constants import BASIC_FONT

# 导入所有工具模块
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

# 初始化日志系统，使用配置文件中的日志级别和日志文件路径
log = log.setup_logging()


tool_datas = {
    "decompiler": {
        "name": "反编译",
        "module": decompiler,
        "has_gui": True,  # 具有独立的GUI界面
    },
    "generate_waves": {
        "name": "生成波次",
        "module": generate_waves,
        "has_gui": True,  # 具有独立的GUI界面
    },
    "process_images": {
        "name": "处理图像",
        "module": process_images,
        "has_gui": True,
    },
    "sort_table": {
        "name": "排序表",
        "module": sort_table,
        "has_gui": False,  # 无GUI，直接运行
    },
    "split_atlas": {
        "name": "拆分图集",
        "module": split_atlas,
        "has_gui": False,
    },
    "generate_atlas": {
        "name": "合并图集",
        "module": generate_atlas,
        "has_gui": True,
    },
    "measure_anchor": {
        "name": "测量锚点",
        "module": measure_anchor,
        "has_gui": True,
    },
    "plist_level_to_lua": {
        "name": "四代关卡数据转换",
        "module": plist_level_to_lua,
        "has_gui": False,
    },
    "plist_animation_to_lua": {
        "name": "四代动画数据转换",
        "module": plist_animation_to_lua,
        "has_gui": False,
    },
    "drag_rename": {
        "name": "拖拽重命名",
        "module": drag_rename,
        "has_gui": True,
    },
}


class MainApplication:
    """
    主应用程序类

    负责创建和管理主窗口界面，包括：
    1. 工具选择按钮
    2. 配置设置功能
    3. 文档显示区域

    Attributes:
        root (tk.Tk): Tkinter根窗口对象
        buttons_frame (ttk.Frame): 按钮容器框架
        texts_frame (ttk.Frame): 文本框容器框架
    """

    def __init__(self, root):
        """
        初始化主应用程序

        Args:
            root (tk.Tk): Tkinter根窗口对象
        """
        self.root = root
        self.root.title("KRTools")  # 窗口标题
        self.root.geometry("1150x500")  # 窗口初始大小

        self.root.columnconfigure(0, weight=1)

        # 创建界面组件
        self.create_widgets()

    def create_widgets(self):
        """创建主界面的所有组件"""
        # 创建工具模块按钮
        self.create_module_buttons()
        # 创建文档显示区域
        self.create_texts()

    def create_module_buttons(self):
        """创建运行各工具模块的按钮"""
        # 创建按钮容器框架
        self.buttons_frame = ttk.Frame(self.root)
        self.buttons_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.buttons_frame.columnconfigure(0, weight=1)

        column = 0
        row = 0
        # 遍历所有工具，为每个工具创建按钮
        for _, data in tool_datas.items():
            name = data["name"]

            btn_frame = ttk.Frame(self.buttons_frame)
            btn_frame.grid(row=row, column=column, sticky="nsew")

            # 创建运行工具的按钮
            btn = ttk.Button(
                btn_frame,
                text=name,
                command=lambda m=data["module"], g=data["has_gui"]: self.run_module(
                    m, g
                ),
                width=15,
            )
            btn.grid(row=row, column=column, padx=5, pady=5)

            column += 1

            if column == 8:
                row += 1
                column = 0

        # 在按钮区域下方添加“全局设置”按钮
        settings_btn = ttk.Button(
            self.buttons_frame,
            text="⚙️ 全局设置",
            command=self.open_global_settings,
            width=15,
        )
        settings_btn.grid(row=row + 1, column=0, columnspan=8, pady=(10, 0))

    def open_global_settings(self):
        """打开集中设置窗口"""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("KRTools 全局设置")
        settings_win.geometry("900x700")
        settings_win.transient(self.root)
        settings_win.grab_set()
        self.center_window(settings_win)

        # 创建Notebook
        notebook = ttk.Notebook(settings_win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 存储每个工具的文本控件引用
        self.tab_text_widgets = {}

        # 为每个工具创建一个标签页
        for key, tool_info in tool_datas.items():
            tool_name = tool_info["name"]
            tab = ttk.Frame(notebook)
            notebook.add(tab, text=tool_name)

            # 创建JSON编辑器框架
            editor_frame = ttk.LabelFrame(
                tab, text=f"{tool_name} 配置 (JSON格式)", padding=5
            )
            editor_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # 创建带行号的编辑器
            text_widget, line_numbers = self.create_json_editor_widgets(
                editor_frame, initial_text=config.setting.get(key, {})
            )

            # 存储文本控件引用
            self.tab_text_widgets[key] = text_widget

            # 为当前标签页添加重置按钮
            reset_btn = ttk.Button(
                tab,
                text="重置为默认",
                command=lambda k=key, tw=text_widget: self.reset_tool_setting(k, tw),
            )
            reset_btn.pack(anchor=tk.E, padx=10, pady=(0, 5))

        # 底部按钮栏
        btn_frame = ttk.Frame(settings_win)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        save_btn = ttk.Button(
            btn_frame, text="保存所有", command=self.save_all_settings
        )
        save_btn.pack(side=tk.RIGHT, padx=5)

        cancel_btn = ttk.Button(btn_frame, text="取消", command=settings_win.destroy)
        cancel_btn.pack(side=tk.RIGHT)

    def create_json_editor_widgets(self, parent, initial_text):
        """
        创建带行号的JSON编辑器，返回 (text_widget, line_numbers_widget)
        """
        # 主水平容器
        main_h = ttk.Frame(parent)
        main_h.pack(fill=tk.BOTH, expand=True)

        # 行号区域
        line_numbers_frame = ttk.Frame(main_h, width=40)
        line_numbers_frame.pack(side=tk.LEFT, fill=tk.Y)
        line_numbers_frame.pack_propagate(False)

        line_numbers = tk.Text(
            line_numbers_frame,
            width=4,
            height=1,
            font=("Consolas", 11),
            bg="#f0f0f0",
            fg="#666666",
            state=tk.DISABLED,
            wrap=tk.NONE,
            relief=tk.FLAT,
            borderwidth=0,
            padx=5,
            pady=5,
        )
        line_numbers.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 编辑器区域
        editor_container = ttk.Frame(main_h)
        editor_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scroll = ttk.Scrollbar(editor_container, orient=tk.VERTICAL)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        h_scroll = ttk.Scrollbar(editor_container, orient=tk.HORIZONTAL)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        text_widget = tk.Text(
            editor_container,
            wrap=tk.NONE,
            font=("Consolas", 11),
            undo=True,
            maxundo=-1,
            yscrollcommand=v_scroll.set,
            xscrollcommand=h_scroll.set,
            padx=10,
            pady=10,
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        v_scroll.config(command=text_widget.yview)
        h_scroll.config(command=text_widget.xview)

        # 插入初始内容
        if isinstance(initial_text, dict):
            formatted = json.dumps(
                initial_text, indent=4, ensure_ascii=False, sort_keys=True
            )
        else:
            formatted = str(initial_text)
        text_widget.insert("1.0", formatted)

        # 绑定事件更新行号
        def refresh_line_numbers(event=None):
            self.update_line_numbers(text_widget, line_numbers)

        text_widget.bind("<KeyRelease>", refresh_line_numbers)
        text_widget.bind("<MouseWheel>", refresh_line_numbers)
        text_widget.bind("<Button-1>", refresh_line_numbers)
        v_scroll.bind("<MouseWheel>", refresh_line_numbers)
        v_scroll.bind("<Button-1>", refresh_line_numbers)
        v_scroll.bind("<B1-Motion>", refresh_line_numbers)
        h_scroll.bind("<MouseWheel>", refresh_line_numbers)
        h_scroll.bind("<Button-1>", refresh_line_numbers)
        h_scroll.bind("<B1-Motion>", refresh_line_numbers)

        # 初始更新行号
        self.update_line_numbers(text_widget, line_numbers)

        return text_widget, line_numbers

    def update_line_numbers(self, text_widget, line_numbers):
        """
        更新行号显示

        Args:
            text_widget: 主文本控件
            line_numbers: 行号文本控件
        """
        # 获取当前行数
        line_count = text_widget.index(tk.END).split(".")[0]

        # 生成行号文本
        line_numbers.config(state=tk.NORMAL)
        line_numbers.delete("1.0", tk.END)

        for i in range(1, int(line_count)):
            line_numbers.insert(tk.END, f"{i}\n")

        line_numbers.config(state=tk.DISABLED)

        # 同步滚动
        top, _ = text_widget.yview()
        line_numbers.yview_moveto(top)

    def reset_tool_setting(self, tool_key, text_widget):
        """将指定工具的设置重置为默认值"""
        if not messagebox.askyesno(
            "确认", f"确定重置 {tool_datas[tool_key]['name']} 为默认配置吗？"
        ):
            return
        try:
            with open(config.default_setting_file, "r", encoding="utf-8") as f:
                default_all = json.load(f)
            default = default_all.get(tool_key, {})
            formatted = json.dumps(
                default, indent=4, ensure_ascii=False, sort_keys=True
            )
            text_widget.delete("1.0", tk.END)
            text_widget.insert("1.0", formatted)
            log.info(f"已重置 {tool_key} 配置")
        except Exception as e:
            log.error(f"❌ 重置失败: {str(e)}")
            messagebox.showerror("错误", f"重置失败: {str(e)}")

    def save_all_settings(self):
        """保存所有工具的配置到文件"""
        try:
            # 收集每个工具的配置
            for key, text_widget in self.tab_text_widgets.items():
                content = text_widget.get("1.0", tk.END).strip()
                if not content:
                    continue
                # 验证JSON
                new_setting = json.loads(content)
                if not isinstance(new_setting, dict):
                    messagebox.showerror(
                        "错误", f"{tool_datas[key]['name']} 的配置必须是JSON对象"
                    )
                    return
                config.setting[key] = new_setting

            # 写入文件
            with open(config.setting_file, "w", encoding="utf-8") as f:
                json.dump(config.setting, f, indent=4, ensure_ascii=False)

            messagebox.showinfo("成功", "所有配置已保存")
            # 关闭窗口
            for widget in self.tab_text_widgets.values():
                widget.master.master.master.master.destroy()  # 简单关闭顶层窗口
            # 或者直接关闭当前活动窗口
            # settings_win = text_widget.master.master.master.master
            # settings_win.destroy()
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON错误", f"格式错误: {str(e)}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def create_texts(self):
        """创建文档显示区域（README和LICENSE）"""
        # 创建文本框容器框架
        self.texts_frame = ttk.Frame(self.root)
        self.texts_frame.grid(row=1, column=0, padx=10, pady=(0, 10))

        self.texts_frame.columnconfigure(0, weight=1)
        self.texts_frame.columnconfigure(1, weight=1)
        self.texts_frame.rowconfigure(0, weight=1)

        # 创建左侧文本框（显示README.md）
        self.create_readme_text()

        # 创建右侧文本框（显示LICENSE.md）
        self.create_license_text()

    def create_readme_text(self):
        """创建README文档显示区域"""
        # 创建带标签的框架
        self.readme_text_frame = ttk.LabelFrame(
            self.texts_frame, text="自述", padding=10
        )
        self.readme_text_frame.grid(row=0, column=0, padx=(0, 5))
        self.readme_text_frame.columnconfigure(0, weight=1)

        # 创建文本控件和滚动条
        self.create_text_widget(self.readme_text_frame, config.readme_file)

    def create_license_text(self):
        """创建LICENSE文档显示区域"""
        # 创建带标签的框架
        self.license_text_frame = ttk.LabelFrame(
            self.texts_frame, text="协议", padding=10
        )
        self.license_text_frame.grid(row=0, column=1, padx=(5, 0))
        self.license_text_frame.columnconfigure(0, weight=1)

        # 创建文本控件和滚动条
        self.create_text_widget(self.license_text_frame, config.license_file)

    def create_text_widget(self, parent_frame, file_name):
        """
        创建带滚动条的文本控件

        Args:
            parent_frame (ttk.Frame): 父框架
            file_name (str): 要加载的文件名
        """
        # 创建文本控件
        text_widget = tk.Text(
            parent_frame,
            wrap=tk.WORD,  # 自动换行
            font=(BASIC_FONT, 12),
            undo=True,  # 启用撤销功能
            maxundo=-1,  # 无限撤销步数
            spacing1=5,  # 行前间距
            spacing3=5,  # 行后间距
        )
        text_widget.grid(row=0, column=0, sticky="nsew")

        # 创建垂直滚动条
        scrollbar = ttk.Scrollbar(
            parent_frame, orient=tk.VERTICAL, command=text_widget.yview
        )
        scrollbar.grid(row=0, column=1, sticky="ns")

        # 配置文本控件的滚动条
        text_widget.config(yscrollcommand=scrollbar.set)

        # 加载并显示文件内容
        try:
            file_path = Path(file_name)
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    text_widget.insert(tk.END, content)
                    text_widget.edit_modified(False)  # 标记为未修改
                    log.info(f"✅ 加载文件: {file_name}")
            else:
                text_widget.insert(tk.END, f"文件 {file_name} 不存在")
                log.warning(f"⚠️ 文件不存在: {file_name}")
        except Exception as e:
            text_widget.insert(tk.END, f"加载文件时出错: {str(e)}")
            log.error(f"❌ 加载文件失败: {file_name} - {str(e)}")

        # 禁用文本编辑（只读模式）
        text_widget.config(state=tk.DISABLED)

        # 存储文本控件的引用
        if file_name == "README.md":
            self.readme_text = text_widget
        elif file_name == "LICENSE.md":
            self.license_text = text_widget

    def run_module(self, module, has_gui):
        """
        运行指定的工具模块

        Args:
            module: 工具模块对象
            has_gui (bool): 该模块是否有独立的GUI界面

        Process:
            1. 更新界面
            2. 检查输入目录
            3. 根据模块类型调用不同的运行方式
        """
        # 更新界面以确保所有更改已应用
        self.root.update_idletasks()

        # 检查输入目录是否为空（仅作为警告，不阻止执行）
        if not any(config.input_path.iterdir()):
            log.warning("⚠️ 输入目录为空，可能不会有输出内容")
            # 可选：显示警告对话框
            # messagebox.showwarning("警告", "输入目录为空，可能不会有输出内容")

        try:
            if has_gui:
                # 有GUI的模块：传递主窗口引用
                log.info(f"🔧 启动带GUI的工具: {module.__name__}")
                module.main(self.root)
            else:
                # 无GUI的模块：直接运行
                log.info(f"🔧 启动命令行工具: {module.__name__}")
                module.main()

        except Exception as e:
            log.error(f"❌ 工具执行失败: {module.__name__} - {str(e)}")
            traceback.print_exc()
            messagebox.showerror("错误", f"工具执行失败: {str(e)}")

    def center_window(self, window):
        """
        将窗口居中显示

        Args:
            window: 要居中的窗口
        """
        window.update_idletasks()

        # 获取屏幕尺寸
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        # 获取窗口尺寸
        window_width = window.winfo_width()
        window_height = window.winfo_height()

        # 计算居中位置
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        # 设置窗口位置
        window.geometry(f"+{x}+{y}")

    def save_setting(self, setting_window, setting_key):
        """
        保存设置到配置文件

        Args:
            setting_window: 设置窗口对象
            setting_key: 设置键名

        Returns:
            bool: 保存是否成功
        """
        try:
            # 获取编辑器中的文本内容
            json_text = setting_window.text_widget.get("1.0", tk.END).strip()

            if not json_text:
                messagebox.showwarning("警告", "配置内容不能为空")
                return False

            # 验证JSON格式
            new_setting = json.loads(json_text)

            # 验证数据结构（简单检查）
            if not isinstance(new_setting, dict):
                messagebox.showerror("错误", "配置必须是JSON对象格式")
                return False

            # 更新配置（合并而不是替换，保留其他键）
            config.setting[setting_key] = new_setting

            # 保存到文件
            with open(config.setting_file, "w", encoding="utf-8") as f:
                json.dump(config.setting, f, indent=4, ensure_ascii=False)

            log.info(f"✅ 保存配置: {setting_key}")
            messagebox.showinfo("成功", "配置保存成功")

            # 关闭设置窗口
            setting_window.destroy()

            return True

        except json.JSONDecodeError as e:
            error_msg = f"JSON格式错误:\n第{e.lineno}行，第{e.colno}列\n{e.msg}"
            messagebox.showerror("JSON错误", error_msg)
            log.error(f"❌ JSON解析失败: {str(e)}")
            return False
        except Exception as e:
            error_msg = f"保存配置时出错:\n{str(e)}"
            messagebox.showerror("错误", error_msg)
            log.error(f"❌ 保存配置失败: {str(e)}")
            traceback.print_exc()
            return False

    def reset_setting(self, setting_window, setting_key):
        """
        重置为默认设置

        Args:
            setting_window: 设置窗口对象
            setting_key: 设置键名
        """
        # 确认对话框
        if not messagebox.askyesno("确认", "确定要恢复默认设置吗？"):
            return

        try:
            with open(config.default_setting_file, "r", encoding="utf-8") as f:
                default_setting = json.load(f)

            current_default_setting = default_setting[setting_key]

            config.setting[setting_key] = current_default_setting

            # 更新编辑器内容
            formatted_json = json.dumps(
                current_default_setting, indent=4, ensure_ascii=False, sort_keys=True
            )

            setting_window.text_widget.delete("1.0", tk.END)
            setting_window.text_widget.insert("1.0", formatted_json)
            setting_window.text_widget.edit_modified(False)

            # 更新行号
            self.update_line_numbers(
                setting_window.text_widget, setting_window.line_numbers
            )

            log.info(f"🔄 重置配置: {setting_key}")
            messagebox.showinfo("成功", "已重置为默认设置")

        except ImportError:
            messagebox.showerror("错误", "找不到默认配置模块")
            log.error("❌ 导入默认配置模块失败")
        except Exception as e:
            messagebox.showerror("错误", f"重置配置时出错: {str(e)}")
            log.error(f"❌ 重置配置失败: {str(e)}")


def main():
    """
    主函数：启动KRTools应用程序

    Process:
        1. 创建Tkinter根窗口
        2. 初始化主应用程序
        3. 启动主事件循环
    """
    try:
        # 创建Tkinter根窗口
        root = tk.Tk()

        # 设置应用程序图标（如果存在）
        icon_path = Path("icon.ico")
        if icon_path.exists():
            try:
                root.iconbitmap(str(icon_path))
                log.info("✅ 加载应用程序图标")
            except Exception as e:
                log.warning(f"⚠️ 加载图标失败: {str(e)}")

        # 初始化主应用程序
        app = MainApplication(root)

        # 启动主事件循环
        log.info("🚀 KRTools应用程序启动")
        root.mainloop()

        log.info("👋 KRTools应用程序正常退出")

    except Exception as e:
        log.error(f"❌ 应用程序启动失败: {str(e)}")
        traceback.print_exc()
        messagebox.showerror("致命错误", f"应用程序启动失败:\n{str(e)}")


if __name__ == "__main__":
    # 设置异常处理钩子，捕获未处理的异常
    import sys

    def exception_handler(exc_type, exc_value, exc_traceback):
        """全局异常处理函数"""
        log.critical("未捕获的异常", exc_info=(exc_type, exc_value, exc_traceback))
        messagebox.showerror(
            "未处理的异常",
            f"发生未处理的异常:\n\n类型: {exc_type.__name__}\n"
            f"信息: {str(exc_value)}\n\n"
            f"详细信息请查看日志文件。",
        )
        sys.exit(1)

    sys.excepthook = exception_handler

    # 运行主函数
    main()
