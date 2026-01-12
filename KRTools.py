import subprocess, json, traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import config

import Tools.generate_waves as generate_waves
import Tools.process_images as process_images
import Tools.sort_table as sort_table
import Tools.split_atlas as split_atlas
import Tools.generate_atlas as generate_atlas
import Tools.measure_anchor as measure_anchor
import Tools.plist_level_to_lua as plist_level_to_lua
import Tools.plist_animation_to_lua as plist_animation_to_lua

import log

log = log.setup_logging(config.log_level, config.log_file)


def get_tools_data():
    return {
        "generate_waves": {
            "name": "生成波次",
            "module": generate_waves,
            "has_gui": True,
        },
        "process_images": {
            "name": "处理图像",
            "module": process_images,
            "has_gui": True,
        },
        "sort_table": {
            "name": "排序表",
            "module": sort_table,
            "has_gui": False,
        },
        "split_atlas": {
            "name": "拆分图集",
            "module": split_atlas,
            "has_gui": False,
        },
        "generate_atlas": {
            "name": "合并图集",
            "module": generate_atlas,
            "has_gui": False,
        },
        "measure_anchor": {
            "name": "测量锚点",
            "module": measure_anchor,
            "has_gui": True,
        },
        "plist_level_to_lua": {
            "name": "四代关卡数据转五代",
            "module": plist_level_to_lua,
            "has_gui": False,
        },
        "plist_animation_to_lua": {
            "name": "四代动画数据转五代",
            "module": plist_animation_to_lua,
            "has_gui": False,
        },
    }


class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("KRTools")
        self.root.geometry("1050x400")

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建界面组件"""
        # 运行其他模块的按钮
        self.create_module_buttons()
        self.create_texts()

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

    def create_module_buttons(self):
        """创建运行其他模块的按钮"""

        self.buttons_frame = ttk.Frame(self.root)
        self.buttons_frame.grid(row=0, column=0)

        i = 0
        for key, value in get_tools_data().items():
            name = value["name"]
            btn = ttk.Button(
                self.buttons_frame,
                text=name,
                command=lambda m=value["module"], g=value["has_gui"]: self.run_module(
                    m, g
                ),
            )
            btn.grid(row=0, column=i, pady=5, padx=5, sticky=(tk.W, tk.E))

            if config.setting.get(key):
                setting_btn = ttk.Button(
                    self.buttons_frame,
                    text=name + "设置",
                    command=lambda k=key: self.open_setting(k),
                )
                setting_btn.grid(row=1, column=i, pady=5, padx=5, sticky=(tk.W, tk.E))
            i += 1
        # 配置按钮框架的网格
        self.buttons_frame.columnconfigure(0, weight=1)

    def create_texts(self):
        self.texts_frame = ttk.Frame(self.root)
        self.texts_frame.grid(
            row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10
        )

        # 配置网格权重，使Frame可以扩展
        self.texts_frame.columnconfigure(0, weight=1)
        self.texts_frame.columnconfigure(1, weight=1)
        self.texts_frame.rowconfigure(0, weight=1)

        # 第一个文本框（左边）
        self.readme_text_frame = ttk.LabelFrame(
            self.texts_frame, text="自述", padding=10
        )
        self.readme_text_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # 创建垂直滚动条
        self.readme_text_scrollbar = ttk.Scrollbar(self.readme_text_frame)
        self.readme_text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建多行文本框并关联滚动条
        self.readme_text = tk.Text(
            self.readme_text_frame,
            width=40,
            height=10,
            font=("Arial", 12),
            yscrollcommand=self.readme_text_scrollbar.set,
        )
        with open("README.md", "r", encoding="utf-8") as f:
            self.readme_text.insert(tk.END, f.read())
        self.readme_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.readme_text_scrollbar.config(command=self.readme_text.yview)

        # 第二个文本框（右边）
        self.about_text_frame = ttk.LabelFrame(
            self.texts_frame, text="协议", padding=10
        )
        self.about_text_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        # 创建垂直滚动条
        self.about_text_scrollbar = ttk.Scrollbar(self.about_text_frame)
        self.about_text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建多行文本框并关联滚动条
        self.about_text = tk.Text(
            self.about_text_frame,
            width=40,
            height=10,
            font=("Arial", 12),
            yscrollcommand=self.about_text_scrollbar.set,
        )
        with open("LICENSE.md", "r", encoding="utf-8") as f:
            self.about_text.insert(tk.END, f.read())
        self.about_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.about_text_scrollbar.config(command=self.about_text.yview)

    def run_module(self, module, has_gui):
        self.root.update()

        if not any(config.input_path.iterdir()):
            log.warning("输入目录为空，可能不会有输出内容")

        if has_gui:
            module.main(self.root)
        else:
            module.main()

    def open_setting(self, setting_key):
        """打开设置窗口"""
        setting_window = tk.Toplevel(self.root)
        setting_window.title("设置")
        setting_window.geometry("1600x800")
        setting_window.transient(self.root)
        setting_window.grab_set()

        # 主框架
        main_frame = ttk.Frame(setting_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 创建文本框用于编辑JSON
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        text_label = ttk.Label(text_frame, text="编辑配置 (JSON格式):")
        text_label.pack(anchor=tk.W)

        text_widget = tk.Text(
            text_frame, wrap=tk.WORD, width=80, height=20, font=("Consolas", 12)
        )
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # 插入当前配置
        try:
            formatted_json = json.dumps(
                config.setting[setting_key], indent=4, ensure_ascii=False
            )
            text_widget.insert("1.0", formatted_json)
        except Exception as e:
            messagebox.showerror("错误", f"格式化配置时出错: {traceback.print_exc()}")
            text_widget.insert("1.0", "{}")

        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        # 保存按钮
        save_btn = ttk.Button(
            button_frame,
            text="保存",
            command=lambda: self.save_setting(
                text_widget.get("1.0", tk.END), setting_window, setting_key
            ),
        )
        save_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # 取消按钮
        cancel_btn = ttk.Button(
            button_frame, text="取消", command=setting_window.destroy
        )
        cancel_btn.pack(side=tk.RIGHT)

    def save_setting(self, json_text, parent_window, setting_key):
        """保存设置"""
        try:
            # 验证JSON格式
            new_setting = json.loads(json_text)

            # 更新配置
            config.setting[setting_key].update(new_setting)

            # 保存到文件
            with open(config.setting_file, "w", encoding="utf-8") as f:
                json.dump(config.setting, f, indent=4, ensure_ascii=False)
                parent_window.destroy()

        except json.JSONDecodeError as e:
            messagebox.showerror("错误", f"JSON格式错误: {traceback.print_exc()}")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置时出错: {traceback.print_exc()}")


def main():
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
