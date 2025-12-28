import subprocess, json, traceback
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import config, tools


class MainApplication:
    def __init__(self, root):
        self.root = root
        self.root.title("KRTools")
        self.root.geometry("1300x130")

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建界面组件"""
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.grid(row=0, column=0, columnspan=2)

        # 运行其他模块的按钮
        self.create_module_buttons(buttons_frame)

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

    def create_module_buttons(self, parent):
        """创建运行其他模块的按钮"""
        i = 0
        for key, value in tools.get_tools_data().items():
            name = value["name"]
            module = value["module"]
            has_gui = value["has_gui"]
            btn = ttk.Button(
                parent,
                text=name,
                command=lambda m=module, g=has_gui: self.run_module(m, g),
            )
            btn.grid(row=0, column=i, pady=5, padx=5, sticky=(tk.W, tk.E))

            if config.setting.get(key):
                setting_btn = ttk.Button(
                    parent,
                    text=name + "设置",
                    command=lambda k=key: self.open_setting(k),
                )
                setting_btn.grid(row=1, column=i, pady=5, padx=5, sticky=(tk.W, tk.E))

            i += 1
        # 配置按钮框架的网格
        parent.columnconfigure(0, weight=1)

    def run_module(self, module, has_gui):
        self.root.update()

        if not any(config.input_path.iterdir()):
            print("警告：输入目录为空可能不会有输出内容")

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
