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
        self.root.geometry("700x400")

        self.source_index = None  # 拖拽起始项的索引
        self.press_x = None  # 按下时的鼠标 X 坐标
        self.press_y = None  # 按下时的鼠标 Y 坐标
        self.files = []  # 存储当前目录下的文件列表

        # 关联文件替换相关变量
        self.assoc_path = tk.StringVar()
        self.file_pattern = tk.StringVar()
        self.target_pattern = tk.StringVar()
        self.replace_string = tk.StringVar()

        self.create_widgets()
        self.load_folder()

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 文件列表（带滚动条）
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

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
        ttk.Label(assoc_frame, text="目标正则:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.target_pattern, width=40).grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=2
        )

        # 第四行：替换后增加的字符串
        ttk.Label(assoc_frame, text="替换后增加的字符串:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.replace_string, width=40).grid(
            row=3, column=1, sticky=tk.W, padx=5, pady=2
        )

    def browse_assoc_file(self):
        """打开文件对话框选择关联文件"""
        filename = filedialog.askopenfilename(
            title="选择关联文件", filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if filename:
            self.assoc_path.set(filename)

    def load_folder(self):
        """扫描文件夹，获取所有文件（排除子目录），按名称排序后更新列表"""
        self.files = list(config.input_path.glob("*.*"))
        self.update_listbox()

    def update_listbox(self):
        self.listbox.delete(0, tk.END)
        for i, file in enumerate(self.files, start=1):
            self.listbox.insert(tk.END, f"{i}. {file.name}")

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

            os.replace(path1, temp_path)
            os.replace(path2, path1)
            os.replace(temp_path, path2)

            log.info(f"交换：{path1.name} <-> {path2.name}")

            # 执行文本交换
            assoc_file = self.assoc_path.get().strip()
            if assoc_file and os.path.isfile(assoc_file):
                self.swap_in_assoc_file(path1, path2, assoc_file)

            # 重新加载文件列表以反映新文件名
            self.load_folder()

        except Exception as e:
            log.error(f"❌ 交换失败: {e} - {traceback.format_exc()}")
            messagebox.showerror("交换失败", f"无法交换文件：{e}")

    def swap_in_assoc_file(self, text1, text2, assoc_path):
        """
        在关联文件中安全地交换 text1 和 text2 两个字符串。
        若提供了正则表达式，则用其从 text1/text2 中提取实际要交换的子串。
        """
        file_pattern = self.file_pattern.get()
        target_pattern = self.target_pattern.get()

        try:
            # 1. 确定实际要交换的字符串
            if file_pattern:
                regex = re.compile(file_pattern)
                match1 = regex.search(text1.name)
                match2 = regex.search(text2.name)
                if match1 and match2:
                    replace1 = match1.group(0)
                    replace2 = match2.group(0)
            else:
                replace1, replace2 = text1.stem, text2.stem

            if replace1 == replace2:
                return  # 无需替换

            # 2. 读取关联文件内容
            with open(assoc_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 3. 处理目标正则
            if target_pattern:
                number_match = re.search(r"\d+$", text1.stem)
                if number_match:
                    number = number_match.group()
                    target1_pattern = target_pattern.replace("%X", number)

                number_match = re.search(r"\d+$", text2.stem)
                if number_match:
                    number = number_match.group()
                    target2_pattern = target_pattern.replace("%X", number)

                match1 = re.search(target1_pattern, content)
                match2 = re.search(target2_pattern, content)
                if match1 and match2:
                    target1 = match1.group()
                    target2 = match2.group()
            else:
                target1, target2 = text1.stem, text2.stem

            if self.replace_string.get():
                splited_replace_string = self.replace_string.get().split("%X")
                if len(splited_replace_string) >= 1:
                    replace1 = splited_replace_string[0] + replace1
                    replace2 = splited_replace_string[0] + replace2

                if len(splited_replace_string) == 2:
                    replace1 += splited_replace_string[1]
                    replace2 += splited_replace_string[1]

            # 4. 安全交换（使用临时占位符）
            target1_placeholder = f"__TEMP_{uuid.uuid4().hex}__"
            new_content = content.replace(target1, target1_placeholder, 1)

            new_content = new_content.replace(target2, replace1, 1)
            new_content = new_content.replace(target1_placeholder, replace2, 1)

            # 4. 写回文件
            with open(assoc_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            log.info(f"关联文件 {assoc_path} 中已交换 '{target1}' <-> '{target2}'")

        except Exception as e:
            log.error(f"❌ 关联文件替换失败: {e} - {traceback.format_exc()}")
            messagebox.showerror("替换失败", f"关联文件替换失败：{e}")


def main(root=None):
    global setting
    setting = config.setting["drag_rename"]

    run_app(root, DragRenameApp)
