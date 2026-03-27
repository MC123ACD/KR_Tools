import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, uuid, traceback, re
from pathlib import Path
import lib.config as config
from lib.utils import run_app
import lib.log as log

log = log.setup_logging()


class DragRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("拖拽重命名工具")
        self.root.geometry("700x500")

        self.source_index = None  # 拖拽起始项的索引
        self.press_x = None  # 按下时的鼠标 X 坐标
        self.press_y = None  # 按下时的鼠标 Y 坐标
        self.scroll_pos = None  # 滚动位置
        self.files = []  # 存储当前目录下的文件列表

        # 关联文件替换相关变量
        self.assoc_path = tk.StringVar()
        self.file_pattern = tk.StringVar()
        self.target_pattern = tk.StringVar()
        self.extra_string = tk.StringVar()

        self.create_widgets()
        self.load_folder()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=5)

        refresh_btn = ttk.Button(folder_frame, text="刷新", command=self.load_folder)
        refresh_btn.pack(side=tk.RIGHT)

        # 文件列表（带滚动条）
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set, selectmode=tk.SINGLE, font=("Microsoft YaHei", 12)
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.listbox.yview)

        # 绑定鼠标事件
        self.listbox.bind("<ButtonPress-1>", self.on_press)
        self.listbox.bind("<ButtonRelease-1>", self.on_release)

        assoc_frame = ttk.LabelFrame(main_frame, text="关联文件替换", padding="5")
        assoc_frame.pack(fill=tk.X, pady=5)

        # 第一行：文件路径 + 浏览按钮
        ttk.Label(assoc_frame, text="文件路径:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.assoc_path, width=40).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=2
        )
        ttk.Button(assoc_frame, text="浏览", command=self.browse_assoc_file).grid(
            row=0, column=2, padx=5, pady=2
        )

        # 第二行：文件名正则输入
        ttk.Label(assoc_frame, text="文件名正则:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.file_pattern, width=40).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=2
        )

        # 第三行：目标正则输入
        ttk.Label(assoc_frame, text="目标模式:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.target_pattern, width=40).grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=2
        )

        # 第四行：前后缀
        ttk.Label(assoc_frame, text="前后缀:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.extra_string, width=40).grid(
            row=3, column=1, sticky=tk.W, padx=5, pady=2
        )

    def browse_assoc_file(self):
        """打开文件对话框选择关联文件"""
        filename = filedialog.askopenfilename(
            title="选择关联文件", filetypes=[("所有文件", "*.*")]
        )
        if filename:
            self.assoc_path.set(filename)

    def load_folder(self):
        """扫描文件夹，获取所有文件（排除子目录），按名称排序后更新列表"""
        self.scroll_pos = self.listbox.yview()[0]

        self.files = list(config.input_path.glob("*.*"))
        self.update_listbox()

    def update_listbox(self):
        self.listbox.delete(0, tk.END)
        for i, file in enumerate(self.files, start=1):
            self.listbox.insert(tk.END, f"{i}. {file.name}")

        if self.scroll_pos is not None:
            self.listbox.yview_moveto(self.scroll_pos)

    def on_press(self, event):
        """鼠标按下：记录起始项和坐标，并手动选中该项"""
        self.source_index = self.listbox.nearest(event.y)
        if 0 <= self.source_index < len(self.files):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(self.source_index)
            self.listbox.activate(self.source_index)
        self.press_x = event.x
        self.press_y = event.y
        self.listbox.config(cursor="fleur")
        return "break"

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
                self.files
            ):
                self.swap_files(self.source_index, target_index)

        # 重置拖拽状态
        self.source_index = None
        self.press_x = self.press_y = None

    def swap_files(self, idx1, idx2):
        """交换两个文件的完整名称，并处理关联文件替换"""
        path1 = self.files[idx1]
        path2 = self.files[idx2]

        try:
            # 三阶段重命名交换文件
            temp_name = f"__temp_{uuid.uuid4().hex}_{path2.name}"
            temp_path = config.input_path / temp_name

            # 执行文本交换
            assoc_file = self.assoc_path.get().strip()
            if assoc_file and os.path.isfile(assoc_file):
                if not self.swap_in_assoc_file(path1, path2, assoc_file):
                    return

            os.replace(path1, temp_path)
            os.replace(path2, path1)
            os.replace(temp_path, path2)

            log.info(f"交换：{path1.name} <-> {path2.name}")

            # 重新加载文件列表以反映新文件名
            self.load_folder()

        except Exception as e:
            log.error(f"❌ 交换失败: {e} - {traceback.format_exc()}")
            messagebox.showerror("交换失败", f"无法交换文件：{e}")

    def swap_in_assoc_file(self, path1, path2, assoc_path) -> bool:
        """
        在关联文件中交换与两个文件名相关的字符串。
        返回 True 表示成功，False 表示无需交换或出错。
        """
        file_pattern = self.file_pattern.get().strip()
        target_pattern = self.target_pattern.get().strip()
        extra = self.extra_string.get().strip()

        try:
            # 1. 从文件名提取核心信息（支持捕获组）
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
                # 提取所有捕获组，如果没有组则用整个匹配
                groups1 = match1.groups() or (match1.group(0))
                groups2 = match2.groups() or (match2.group(0))
            else:
                # 未提供文件名正则，则使用整个文件名作为核心信息
                groups1 = stem1
                groups2 = stem2

            # 2. 如果提供了目标模式，则用它构建实际要查找的字符串
            if target_pattern:
                # 用提取的组格式化目标模式（支持 {0}, {1} 等）
                try:
                    target_str1 = target_pattern.format(*groups1)
                    target_str2 = target_pattern.format(*groups2)
                except IndexError:
                    err_msg = "目标模式中使用了超出范围的捕获组索引"
                    log.error(err_msg)
                    messagebox.showerror("参数错误", err_msg)
                    return False
            else:
                # 未提供目标模式，则直接使用核心字符串作为目标
                target_str1 = groups1[0]  # 使用第一个组（或整个字符串）
                target_str2 = groups2[0]

            # 如果两个目标字符串相同，则无需交换
            if target_str1 == target_str2:
                return False

            # 3. 处理前后缀（extra 中可包含 %X 分隔前缀和后缀）
            if extra:
                parts = extra.split("%X")
                prefix = parts[0]
                suffix = parts[1] if len(parts) > 1 else ""
                # 对要插入的字符串添加前后缀（注意：这里交换的是核心组，不是目标字符串）
                # 通常我们交换的是从文件名提取的核心信息，所以对 groups 应用前后缀
                insert1 = prefix + groups1[0] + suffix
                insert2 = prefix + groups2[0] + suffix
            else:
                insert1 = groups1[0]
                insert2 = groups2[0]

            # 4. 读取关联文件内容
            with open(assoc_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not content.find(target_str1) or not content.find(target_str2):
                err_msg = f"目标模式未匹配: {target_str1} 或 {target_str2}"
                log.error(err_msg)
                messagebox.showerror("匹配失败", err_msg)
                return False

            # 5. 安全交换（使用临时占位符）
            # 注意：这里我们交换的是 target_str1 和 target_str2 这两个文本片段，
            # 将它们分别替换为 insert2 和 insert1（交叉替换）
            placeholder = f"__TEMP_{uuid.uuid4().hex}__"
            # 先替换第一个目标为占位符
            new_content = content.replace(target_str1, placeholder, 1)
            # 再替换第二个目标为 insert1
            new_content = new_content.replace(target_str2, insert1, 1)
            # 最后将占位符替换为 insert2
            new_content = new_content.replace(placeholder, insert2, 1)

            # 6. 写回文件
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
