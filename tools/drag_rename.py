import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import uuid
import traceback
import re
from pathlib import Path
import lib.config as config
from lib.utils import run_app
import lib.log as log

log = log.setup_logging()


class DragRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("拖拽重命名工具")
        self.root.geometry("750x550")

        # 从配置读取拖拽阈值
        self.drag_threshold = setting["drag_threshold"]

        # 拖拽状态
        self.source_index = None
        self.press_x = None
        self.press_y = None
        self.scroll_pos = None

        # 文件列表及显示控制
        self.files = []  # 当前显示的文件列表（已排序/过滤）
        self.all_files = []  # 原始文件列表（用于过滤）
        self.sort_by = "name"  # 排序字段: name, mtime, size
        self.filter_text = ""  # 过滤文本

        # 撤销栈 (保存 (path1, path2) 元组)
        self.undo_stack = []
        self.undo_limit = 20

        # 关联文件替换相关变量
        self.assoc_path = tk.StringVar()
        self.file_pattern = tk.StringVar()
        self.target_pattern = tk.StringVar()
        self.extra_string = tk.StringVar()

        self.create_widgets()
        self.load_folder()

        # 绑定全局撤销快捷键
        self.root.bind_all("<Control-z>", self.undo_last_swap)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ---- 工具栏（排序 + 过滤 + 刷新）----
        tool_frame = ttk.Frame(main_frame)
        tool_frame.pack(fill=tk.X, pady=5)

        # 排序下拉
        ttk.Label(tool_frame, text="排序:").pack(side=tk.LEFT, padx=(0, 5))
        self.sort_var = tk.StringVar(value="名称")
        sort_combo = ttk.Combobox(
            tool_frame,
            textvariable=self.sort_var,
            values=["名称", "修改时间", "大小"],
            state="readonly",
            width=10,
        )
        sort_combo.pack(side=tk.LEFT, padx=(0, 10))
        sort_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_sort_filter())

        # 过滤输入框
        ttk.Label(tool_frame, text="过滤:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_entry = ttk.Entry(tool_frame, width=20)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.filter_entry.bind("<KeyRelease>", lambda e: self.apply_sort_filter())

        # 撤销按钮
        undo_btn = ttk.Button(tool_frame, text="撤销", command=self.undo_last_swap)
        undo_btn.pack(side=tk.RIGHT)

        # 刷新按钮
        refresh_btn = ttk.Button(tool_frame, text="刷新", command=self.load_folder)
        refresh_btn.pack(side=tk.RIGHT)

        # ---- 文件列表区域 ----
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            font=("Microsoft YaHei", 12),
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # 绑定鼠标事件（拖拽视觉反馈）
        self.listbox.bind("<ButtonPress-1>", self.on_press)
        self.listbox.bind("<B1-Motion>", self.on_motion)  # 实时高亮目标
        self.listbox.bind("<ButtonRelease-1>", self.on_release)

        # ---- 关联文件替换区域 ----
        assoc_frame = ttk.LabelFrame(main_frame, text="关联文件替换", padding="5")
        assoc_frame.pack(fill=tk.X, pady=5)

        # 文件路径
        ttk.Label(assoc_frame, text="文件路径:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.assoc_path, width=40).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=2
        )
        ttk.Button(assoc_frame, text="浏览", command=self.browse_assoc_file).grid(
            row=0, column=2, padx=5, pady=2
        )

        # 文件名正则
        ttk.Label(assoc_frame, text="文件名正则:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.file_pattern, width=40).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=2
        )

        # 目标模式
        ttk.Label(assoc_frame, text="目标模式:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.target_pattern, width=40).grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=2
        )

        # 前后缀
        ttk.Label(assoc_frame, text="前后缀 (用%X分隔):").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.extra_string, width=40).grid(
            row=3, column=1, sticky=tk.W, padx=5, pady=2
        )

    def browse_assoc_file(self):
        filename = filedialog.askopenfilename(
            title="选择关联文件", filetypes=[("所有文件", "*.*")]
        )
        if filename:
            self.assoc_path.set(filename)

    # ---------- 文件列表管理 ----------
    def load_folder(self):
        """扫描文件夹，获取所有文件，应用排序和过滤后刷新列表"""
        # 保存滚动位置
        self.scroll_pos = self.listbox.yview()[0]

        # 获取所有文件
        self.all_files = list(config.input_path.glob("*.*"))
        self.apply_sort_filter()

    def apply_sort_filter(self):
        """根据当前排序和过滤条件更新 self.files 和列表框"""
        # 1. 过滤
        self.filter_text = self.filter_entry.get().strip()
        if self.filter_text:
            pattern = re.compile(re.escape(self.filter_text), re.IGNORECASE)
            files = [f for f in self.all_files if pattern.search(f.name)]
        else:
            files = self.all_files.copy()

        # 2. 排序
        sort_key = self.sort_var.get()
        if sort_key == "名称":
            files.sort(key=lambda f: f.name)
        elif sort_key == "修改时间":
            files.sort(key=lambda f: f.stat().st_mtime)
        elif sort_key == "大小":
            files.sort(key=lambda f: f.stat().st_size)

        self.files = files
        self.update_listbox()

    def update_listbox(self):
        self.listbox.delete(0, tk.END)
        for i, file in enumerate(self.files, start=1):
            self.listbox.insert(tk.END, f"{i}. {file.name}")
        if self.scroll_pos is not None:
            self.listbox.yview_moveto(self.scroll_pos)

    # ---------- 拖拽交互 ----------
    def on_press(self, event):
        self.source_index = self.listbox.nearest(event.y)
        if 0 <= self.source_index < len(self.files):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.source_index)
            self.listbox.activate(self.source_index)
        self.press_x = event.x
        self.press_y = event.y
        self.listbox.config(cursor="fleur")
        return "break"

    def on_motion(self, event):
        """拖拽过程中高亮当前悬停项"""
        idx = self.listbox.nearest(event.y)
        if 0 <= idx < len(self.files):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(idx)

    def on_release(self, event):
        self.listbox.config(cursor="")
        if self.source_index is None or self.press_x is None:
            return

        # 计算移动距离
        dx = event.x - self.press_x
        dy = event.y - self.press_y
        distance = (dx**2 + dy**2) ** 0.5

        target_index = self.listbox.nearest(event.y)
        if distance >= self.drag_threshold:
            if target_index != self.source_index and 0 <= target_index < len(
                self.files
            ):
                self.swap_files(self.source_index, target_index)

        # 重置状态
        self.source_index = None
        self.press_x = self.press_y = None

    # ---------- 文件交换核心 ----------
    def swap_files(self, idx1, idx2):
        """交换两个文件，并处理关联文件替换。成功则压入撤销栈"""
        path1 = self.files[idx1]
        path2 = self.files[idx2]

        try:
            # 临时文件名
            temp_name = f"__temp_{uuid.uuid4().hex}_{path2.name}"
            temp_path = config.input_path / temp_name

            # 关联文件交换（带预览确认）
            assoc_file = self.assoc_path.get().strip()
            if assoc_file and os.path.isfile(assoc_file):
                if not self.swap_in_assoc_file(path1, path2, assoc_file):
                    return  # 用户取消或失败

            # 三阶段重命名交换文件
            os.replace(path1, temp_path)
            os.replace(path2, path1)
            os.replace(temp_path, path2)

            log.info(f"交换：{path1.name} <-> {path2.name}")

            # 压入撤销栈
            self.push_undo((path1, path2))

            # 重新加载列表
            self.load_folder()

        except PermissionError as e:
            log.error(f"权限错误: {e}")
            messagebox.showerror(
                "权限不足", f"无法交换文件：{e}\n请检查文件是否被其他程序占用。"
            )
        except Exception as e:
            log.error(f"❌ 交换失败: {e} - {traceback.format_exc()}")
            messagebox.showerror("交换失败", f"无法交换文件：{e}")

    def push_undo(self, swap_info):
        """压入撤销栈，限制大小"""
        self.undo_stack.append(swap_info)
        if len(self.undo_stack) > self.undo_limit:
            self.undo_stack.pop(0)

    def undo_last_swap(self, event=None):
        """撤销上一次交换"""
        if not self.undo_stack:
            messagebox.showinfo("撤销", "没有可撤销的操作")
            return

        path1, path2 = self.undo_stack.pop()
        # 由于交换是可逆的，直接再次交换这两个文件即可
        # 需要找到它们在当前文件列表中的索引（可能在过滤/排序后位置不同）
        try:
            # 在 all_files 中找索引（用于恢复关联文件）
            # 但撤销时我们重新交换物理文件，不需要索引
            self.swap_two_files(path1, path2)
            self.load_folder()
        except Exception as e:
            log.error(f"撤销失败: {e}")
            messagebox.showerror("撤销失败", f"无法撤销交换：{e}")

    def swap_two_files(self, path1, path2):
        """仅交换两个物理文件，用于撤销。"""
        temp_name = f"__temp_{uuid.uuid4().hex}_{path2.name}"
        temp_path = config.input_path / temp_name

        # 关联文件交换（撤销时直接交换，不预览）
        assoc_file = self.assoc_path.get().strip()
        if assoc_file and os.path.isfile(assoc_file):
            if not self.swap_in_assoc_file(path1, path2, assoc_file, preview=False):
                return

        os.replace(path1, temp_path)
        os.replace(path2, path1)
        os.replace(temp_path, path2)
        log.info(f"撤销交换：{path1.name} <-> {path2.name}")

    # ---------- 关联文件交换（带预览）----------
    def swap_in_assoc_file(self, path1, path2, assoc_path, preview=True) -> bool:
        """在关联文件中交换两个文件名相关的字符串。
        如果 preview=True，则显示确认对话框。
        """
        file_pattern = self.file_pattern.get().strip()
        target_pattern = self.target_pattern.get().strip()
        extra = self.extra_string.get().strip()

        try:
            # 提取核心信息
            stem1, stem2 = path1.stem, path2.stem
            if file_pattern:
                regex = re.compile(file_pattern)
                match1 = regex.search(stem1)
                match2 = regex.search(stem2)
                if not match1 or not match2:
                    err_msg = f"文件名正则未匹配: {stem1} 或 {stem2}"
                    log.error(err_msg)
                    messagebox.showerror("匹配失败", err_msg)
                    return False
                groups1 = match1.groups() or (match1.group(0),)
                groups2 = match2.groups() or (match2.group(0),)
            else:
                groups1 = (stem1,)
                groups2 = (stem2,)

            # 构建目标字符串
            if target_pattern:
                try:
                    target_str1 = target_pattern.format(*groups1)
                    target_str2 = target_pattern.format(*groups2)
                except IndexError:
                    err_msg = "目标模式中使用了超出范围的捕获组索引"
                    log.error(err_msg)
                    messagebox.showerror("参数错误", err_msg)
                    return False
            else:
                target_str1 = groups1[0]
                target_str2 = groups2[0]

            # 构建要插入的字符串（前后缀处理）
            if extra:
                parts = extra.split("%X")
                prefix = parts[0]
                suffix = parts[1] if len(parts) > 1 else ""
                insert1 = prefix + groups1[0] + suffix
                insert2 = prefix + groups2[0] + suffix
            else:
                insert1 = groups1[0]
                insert2 = groups2[0]

            # 读取文件内容
            with open(assoc_path, "r", encoding="utf-8") as f:
                content = f.read()

            if content.find(target_str1) == -1 or content.find(target_str2) == -1:
                err_msg = f"目标模式未匹配: {target_str1} 或 {target_str2}"
                log.error(err_msg)
                messagebox.showerror("匹配失败", err_msg)
                return False

            # 预览模式：显示将要进行的替换，请求确认
            if preview:
                preview_msg = (
                    f"将在关联文件中进行以下替换：\n\n"
                    f"'{target_str1}' → '{insert2}'\n"
                    f"'{target_str2}' → '{insert1}'\n\n"
                    f"是否继续？"
                )
                if not messagebox.askyesno("确认替换", preview_msg):
                    return False

            # 执行交换（使用占位符安全替换）
            placeholder = f"__TEMP_{uuid.uuid4().hex}__"
            new_content = content.replace(target_str1, placeholder, 1)
            new_content = new_content.replace(target_str2, insert1, 1)
            new_content = new_content.replace(placeholder, insert2, 1)

            # 写回文件
            with open(assoc_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            log.info(f"关联文件交换成功：'{target_str1}' <-> '{target_str2}'")
            return True

        except Exception as e:
            log.error(f"关联文件替换失败: {e}\n{traceback.format_exc()}")
            messagebox.showerror("替换失败", f"关联文件替换失败：{e}")
            return False


def main(root=None):
    global setting
    setting = config.setting["drag_rename"]

    run_app(root, DragRenameApp)
