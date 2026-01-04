import subprocess, subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


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
        """反编译lua文件"""
        target_folder = self.folder_entry.get()

        try:
            subprocess.run(
                [
                    "luajit-decompiler-v2.exe",
                    str(target_folder),
                    "-s",  # 禁用错误弹窗
                    "-f",  # 始终替换
                    "-o",
                    str("output"),  # 输出目录
                ],
                capture_output=True,
                text=True,
            )
            messagebox.showinfo("完成", "反编译完毕")
        except Exception as e:
            messagebox.showerror("错误", f"无法进行反编译: {str(e)}")


def main():
    # style = ttk.Style()
    # style.configure("TButton", padding=6)
    # style.configure("TEntry", padding=5)

    root = tk.Tk()
    app = LuaJITDecompiler(root)
    root.mainloop()

if __name__ == "__main__":
    main()
