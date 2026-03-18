import subprocess, subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from lib.utils import run_decompiler, run_app

class LuaJITDecompiler:

    def __init__(self, root):
        self.root = root
        self.root.title("反编译")
        self.root.geometry("400x150")

        # 创建UI
        ttk.Label(self.root, text="选择包含LuaJIT字节码的文件夹:").pack(pady=10)

        self.folder_entry = ttk.Entry(self.root, width=40)
        self.folder_entry.pack()

        ttk.Frame(self.root, height=10).pack()  # 空白间隔

        btn_frame = ttk.Frame(self.root)
        btn_frame.pack()

        ttk.Button(btn_frame, text="浏览...", command=self.browse_folder).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="开始反编译", command=self.run_decompiler).pack(
            side=tk.LEFT, padx=5
        )

    def browse_folder(self):
        folder = filedialog.askdirectory(title="选择包含LuaJIT字节码的文件夹")
        if folder:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder)

    def run_decompiler(self):
        target_folder = self.folder_entry.get()

        run_decompiler(target_folder)
        messagebox.showinfo("完成", "反编译完毕")


def main(root=None):
    run_app(root, LuaJITDecompiler)



if __name__ == "__main__":
    main()
