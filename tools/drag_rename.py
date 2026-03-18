import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, uuid, traceback
from pathlib import Path
from datetime import datetime
import lib.config as config
from lib.utils import run_app, save_to_dds
from lib.classes import WriteLua, Point, Size, Rectangle, Bounds
import lib.log as log
log = log.setup_logging()

files = []

class DragRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("拖拽重命名工具")
        self.root.geometry("600x400")

        self.source_index = None  # 拖拽起始项的索引
        self.press_x = None  # 按下时的鼠标 X 坐标
        self.press_y = None  # 按下时的鼠标 Y 坐标

        self.create_widgets()
        self.load_folder()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 文件夹选择区域
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=5)

        # 文件列表（带滚动条）
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.listbox.yview)

        # 绑定鼠标事件
        self.listbox.bind("<ButtonPress-1>", self.on_press)
        self.listbox.bind("<ButtonRelease-1>", self.on_release)
        self.listbox.bind("<B1-Motion>", self.on_motion)

    def load_folder(self):
        """扫描文件夹，获取所有文件（排除子目录），按名称排序后更新列表"""
        global files
        files = list(config.input_path.glob("*.*"))

        self.update_listbox()

    def update_listbox(self):
        self.listbox.delete(0, tk.END)
        for i, file in enumerate(files, start=1):
            self.listbox.insert(tk.END, f"{i}. {file.name}")

    def on_press(self, event):
        """鼠标按下：记录起始项和坐标，并手动选中该项（阻止默认选中行为）"""
        self.source_index = self.listbox.nearest(event.y)
        if 0 <= self.source_index < len(files):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.source_index)
            self.listbox.activate(self.source_index)
        self.press_x = event.x
        self.press_y = event.y
        self.listbox.config(cursor="fleur")
        return "break"  # 阻止 Listbox 默认的选中/拖动行为

    def on_release(self, event):
        """鼠标释放：判断是否为有效拖拽，若是则执行交换"""
        self.listbox.config(cursor="")

        # 没有有效起始点则忽略
        if self.source_index is None or self.press_x is None:
            return

        # 计算鼠标移动距离
        dx = event.x - self.press_x
        dy = event.y - self.press_y
        distance = (dx**2 + dy**2) ** 0.5

        # 获取释放位置对应的项索引
        target_index = self.listbox.nearest(event.y)

        # 只有当移动距离超过阈值、且目标索引有效且与源不同时，才执行交换
        if distance >= setting["drag_threshold"]:
            if target_index != self.source_index and 0 <= target_index < len(
                files
            ):
                self.swap_files(self.source_index, target_index)

        # 重置拖拽状态
        self.source_index = None
        self.press_x = self.press_y = None

    def swap_files(self, idx1, idx2):
        """交换两个文件的完整名称（包括扩展名），并记录日志"""
        path1 = files[idx1]
        path2 = files[idx2]

        try:
            # 生成唯一临时文件名（保证不与现有文件冲突）
            temp_name = f"__temp_{uuid.uuid4().hex}_{path2.name}"
            temp_path = config.input_path / temp_name

            # 执行三阶段重命名（使用 os.replace 支持跨平台覆盖）
            os.replace(path1, temp_path)  # 源文件 → 临时文件
            os.replace(path2, path1)  # 目标文件 → 源文件位置
            os.replace(temp_path, path2)  # 临时文件 → 目标文件位置

            # 重新加载文件夹以更新列表（反映新文件名和排序）
            self.load_folder()
            log.info(f"交换：{path1.name} <-> {path2.name}")

        except Exception as e:
            log.error(f"❌ 交换失败: {e} - {traceback.format_exc()}")
            messagebox.showerror("交换失败", f"无法交换文件：{e}")


def main(root=None):
    global setting
    setting = config.setting["drag_rename"]

    run_app(root, DragRenameApp)
