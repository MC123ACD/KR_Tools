import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import uuid
import traceback
import re
from pathlib import Path
from PIL import Image, ImageTk  # 新增：用于生成缩略图
import lib.config as config
from lib.utils import run_app
import lib.log as log

log = log.setup_logging()


class DragRenameApp:
    def __init__(self, root):
        self.root = root
        self.root.title("拖拽重命名工具")
        self.root.geometry("1130x720")

        self.style = ttk.Style()
        self.style.configure("Treeview", rowheight=setting["thumbnail_size"][1])
        self.style.configure(
            "Custom.Treeview",
            rowheight=setting["thumbnail_size"][1],
            font=("Microsoft YaHei", 11),
        )

        # 拖拽状态
        self.source_item = None  # 源 Treeview item ID
        self.press_x = None
        self.press_y = None
        self.scroll_pos = None

        # 文件列表及显示控制
        self.files = []  # 当前显示的文件列表（已排序/过滤）
        self.all_files = []  # 原始文件列表（用于过滤）
        self.sort_by = "name"  # 排序字段: name, mtime, size
        self.filter_text = ""  # 过滤文本

        # 缩略图缓存（保持 PhotoImage 对象的引用）
        self.thumb_cache = {}

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
        main_frame.grid(row=0, column=0)

        # ---- 文件列表区域----
        editor_frame = ttk.Frame(main_frame)
        editor_frame.grid(row=0, column=0, padx=5, pady=5)

        # ---- 工具栏（排序 + 过滤 + 刷新）----
        tool_frame = ttk.Frame(editor_frame)
        tool_frame.pack(fill=tk.X, padx=5, pady=5)

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
        undo_btn.pack(side=tk.RIGHT, padx=5)

        # 刷新按钮
        refresh_btn = ttk.Button(tool_frame, text="刷新", command=self.load_folder)
        refresh_btn.pack(side=tk.RIGHT, padx=5)

        # --------------
        list_frame = ttk.Frame(editor_frame)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(5, 5))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建 Treeview，只显示树列（左侧图标 + 文本）
        self.tree = ttk.Treeview(
            list_frame,
            show="tree",
            selectmode="browse",  # 单选模式
            yscrollcommand=scrollbar.set,
            height=13,
            style="Custom.Treeview",
        )
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 5))
        scrollbar.config(command=self.tree.yview)

        # 绑定鼠标事件（拖拽视觉反馈）
        self.tree.bind("<ButtonPress-1>", self.on_press)
        self.tree.bind("<B1-Motion>", self.on_motion)
        self.tree.bind("<ButtonRelease-1>", self.on_release)

        # ---- 关联文件替换区域 ----
        assoc_frame = ttk.LabelFrame(main_frame, text="关联文件替换", padding="5")
        assoc_frame.grid(row=0, column=1, sticky="n")

        entry_width = 30
        ipady = 3

        # 文件路径
        ttk.Label(assoc_frame, text="文件路径:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.assoc_path, width=entry_width).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=2, ipady=ipady
        )
        ttk.Button(assoc_frame, text="浏览", command=self.browse_assoc_file).grid(
            row=0, column=2, padx=5, pady=2
        )

        # 文件名正则
        ttk.Label(assoc_frame, text="文件名正则:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.file_pattern, width=entry_width).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=2, ipady=ipady
        )

        # 目标模式
        ttk.Label(assoc_frame, text="目标模式:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(
            assoc_frame, textvariable=self.target_pattern, width=entry_width
        ).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2, ipady=ipady)

        # 前后缀
        ttk.Label(assoc_frame, text="前后缀 (用%X分隔):").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Entry(assoc_frame, textvariable=self.extra_string, width=entry_width).grid(
            row=3, column=1, sticky=tk.W, padx=5, pady=2, ipady=ipady
        )

    def browse_assoc_file(self):
        filename = filedialog.askopenfilename(
            title="选择关联文件", filetypes=[("所有文件", "*.*")]
        )
        if filename:
            self.assoc_path.set(filename)

    # ---------- 缩略图生成 ----------
    def get_thumbnail(self, filepath):
        """生成文件的缩略图，返回 PhotoImage 对象，并缓存"""
        size = setting["thumbnail_size"]

        # 使用文件路径作为缓存键
        cache_key = filepath.name
        if cache_key in self.thumb_cache:
            return self.thumb_cache[cache_key]

        # 默认缩略图（空白图片）
        default_img = Image.new("RGBA", size, (240, 240, 240, 0))
        photo = ImageTk.PhotoImage(default_img)

        # 仅对常见图片格式生成缩略图
        ext = filepath.suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"):
            try:
                with Image.open(filepath) as img:
                    # 转换为 RGBA 以支持透明度
                    if img.mode not in ("RGBA", "RGB"):
                        img = img.convert("RGBA")
                    img.thumbnail(size, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
            except Exception as e:
                log.warning(f"无法生成缩略图 {filepath}: {e}")

        # 缓存并返回
        self.thumb_cache[cache_key] = photo
        return photo

    # ---------- 文件列表管理 ----------
    def load_folder(self):
        """扫描文件夹，获取所有文件，应用排序和过滤后刷新列表"""
        # 保存滚动位置
        self.scroll_pos = self.tree.yview()[0]

        # 获取所有文件
        self.all_files = list(config.input_path.glob("*.*"))
        self.apply_sort_filter()

    def apply_sort_filter(self):
        """根据当前排序和过滤条件更新 self.files 和 Treeview"""
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
        self.refresh_treeview()

    def refresh_treeview(self):
        """清空 Treeview 并根据 self.files 重新填充，显示缩略图和文件名"""
        self.thumb_cache.clear()

        self.tree.delete(*self.tree.get_children())
        for file in self.files:
            thumb = self.get_thumbnail(file)
            # 插入项，text 显示文件名，image 显示缩略图
            self.tree.insert(
                "",
                "end",
                text=file.name,
                image=thumb,
                values=(str(file),),  # 可存储路径，但此处未使用
            )
        # 恢复滚动位置
        if self.scroll_pos is not None:
            self.tree.yview_moveto(self.scroll_pos)

    # ---------- 拖拽交互 ----------
    def on_press(self, event):
        # 获取鼠标下的项
        item = self.tree.identify_row(event.y)
        if item:
            self.source_item = item
            self.tree.selection_set(item)  # 选中源项
            self.tree.focus(item)

        self.press_x = event.x
        self.press_y = event.y
        self.tree.config(cursor="fleur")
        return "break"

    def on_motion(self, event):
        """拖拽过程中高亮当前悬停项（与源项同时高亮）"""
        if self.source_item is None:
            return

        target = self.tree.identify_row(event.y)
        if target:
            # 同时高亮源项和目标项
            self.tree.selection_set((self.source_item, target))
        else:
            # 移出列表范围，只高亮源项
            self.tree.selection_set(self.source_item)

    def on_release(self, event):
        self.tree.config(cursor="")
        if self.source_item is None or self.press_x is None:
            return

        # 计算移动距离
        dx = event.x - self.press_x
        dy = event.y - self.press_y
        distance = (dx**2 + dy**2) ** 0.5

        target_item = self.tree.identify_row(event.y)
        if (
            distance >= setting["drag_threshold"]
            and target_item
            and target_item != self.source_item
        ):
            # 获取源和目标在 Treeview 中的索引（与 self.files 顺序一致）
            idx1 = self.tree.index(self.source_item)
            idx2 = self.tree.index(target_item)

            if 0 <= idx1 < len(self.files) and 0 <= idx2 < len(self.files):
                self.swap_files(idx1, idx2)

        # 重置状态
        self.source_item = None
        self.press_x = self.press_y = None
        # 恢复选择为无（或保持最后一项，可选）
        self.tree.selection_remove(self.tree.selection())

    def swap_files(self, idx1, idx2):
        """交换两个文件，并处理关联文件替换。成功则压入撤销栈并更新界面"""
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

            # 更新列表（仅更新两个项目）
            self._update_swap_items(idx1, idx2)

        except PermissionError as e:
            log.error(f"权限错误: {e}")
            messagebox.showerror(
                "权限不足", f"无法交换文件：{e}\n请检查文件是否被其他程序占用。"
            )
        except Exception as e:
            log.error(f"❌ 交换失败: {e} - {traceback.format_exc()}")
            messagebox.showerror("交换失败", f"无法交换文件：{e}")

    def swap_two_files(self, path1, path2):
        """仅交换两个物理文件，用于撤销。成功则更新界面"""
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

        # 更新列表（仅更新两个项目）
        self._update_swap_by_paths(path1, path2)

    # ---------- 列表更新辅助方法 ----------
    def _update_swap_items(self, idx1, idx2):
        """交换 self.files 中两个元素，并更新 Treeview 中对应的两项"""
        if idx1 == idx2:
            return
        
        # 交换 Treeview 中的两个项
        # 获取 Treeview 中所有项 ID（顺序与 self.files 一致）
        items = self.tree.get_children()
        if idx1 >= len(items) or idx2 >= len(items):
            log.warning("索引超出 Treeview 范围，跳过更新")
            return
        
        item1 = items[idx1]
        item2 = items[idx2]
        file1 = self.files[idx1]
        file2 = self.files[idx2]

        # 清除缓存（因为两个文件的内容已互换）
        self.thumb_cache.pop(file1.name, None)
        self.thumb_cache.pop(file2.name, None)

        name1 = self.files[idx1].name
        thumb1 = self.get_thumbnail(file2)
        name2 = self.files[idx2].name
        thumb2 = self.get_thumbnail(file1)

        # 更新 item1
        self.tree.item(item1, text=name1, image=thumb2)
        # 更新 item2
        self.tree.item(item2, text=name2, image=thumb1)

    def _update_swap_by_paths(self, path1, path2):
        """根据两个路径，交换 self.files 中的对应元素并更新 Treeview"""
        try:
            idx1 = self.files.index(path1)
            idx2 = self.files.index(path2)
        except ValueError:
            log.warning(f"路径不在列表中: {path1}, {path2}，执行全量刷新")
            self.load_folder()  # 回退到全量刷新
            return
        self._update_swap_items(idx1, idx2)

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
        try:
            self.swap_two_files(path1, path2)
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

        self._update_swap_by_paths(path1, path2)

    # ---------- 关联文件交换（带预览）----------
    def swap_in_assoc_file(self, path1, path2, assoc_path) -> bool:
        """在关联文件中交换两个文件名相关的字符串。"""
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
            if setting["preview_assoc_replace"]:
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
