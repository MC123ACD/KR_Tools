import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import traceback
from pathlib import Path
import utils as U


class MeasureAnchor:
    def __init__(self, root):
        self.root_window = tk.Toplevel(root)
        self.root_window.title("锚点测量工具")
        self.root_window.geometry("1200x900")

        self.image_path = None
        self.image = None
        self.photo = None
        self.scale = 1.0

        # 锚点坐标（相对于图像左上角）
        self.anchor_x = 0
        self.anchor_y = 0
        self.percent_anchor_x = 0.5
        self.percent_anchor_y = 0.5

        # 参考点坐标
        self.ref_x = 0
        self.ref_y = 0

        # 相对偏移
        self.relative_offset_x = 0
        self.relative_offset_y = 0

        # 网格设置
        self.show_grid = tk.BooleanVar(value=True)
        self.grid_size = tk.IntVar(value=32)

        self.setup_ui()

    def setup_ui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧控制面板
        control_frame = ttk.Frame(main_frame, width=250)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        control_frame.pack_propagate(False)

        # 右侧图像显示区域
        self.image_frame = ttk.Frame(main_frame)
        self.image_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 创建画布用于显示图像
        self.canvas = tk.Canvas(self.image_frame, bg="#2d2d2d")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 绑定事件
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # 文件操作区
        file_frame = ttk.LabelFrame(control_frame, text="文件操作", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(file_frame, text="打开图像", command=self.open_image).pack(
            fill=tk.X, pady=2
        )

        # 锚点控制区
        anchor_frame = ttk.LabelFrame(control_frame, text="锚点控制", padding=10)
        anchor_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(anchor_frame, text="锚点 X:").grid(row=0, column=0, sticky=tk.W)
        self.anchor_x_var = tk.StringVar(value="0")
        self.anchor_x_spinbox = ttk.Spinbox(
            anchor_frame,
            from_=0,
            to=9999,
            textvariable=self.anchor_x_var,
            command=self.update_anchor_from_spinbox,
            width=10,
        )
        self.anchor_x_spinbox.grid(row=0, column=1, padx=5)

        ttk.Label(anchor_frame, text="锚点 Y:").grid(row=1, column=0, sticky=tk.W)
        self.anchor_y_var = tk.StringVar(value="0")
        self.anchor_y_spinbox = ttk.Spinbox(
            anchor_frame,
            from_=0,
            to=9999,
            textvariable=self.anchor_y_var,
            command=self.update_anchor_from_spinbox,
            width=10,
        )
        self.anchor_y_spinbox.grid(row=1, column=1, padx=5)

        self.anchor_x_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_anchor_from_spinbox()
        )
        self.anchor_y_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_anchor_from_spinbox()
        )

        ttk.Label(anchor_frame, text="锚点 X(%):").grid(row=2, column=0, sticky=tk.W)
        self.percent_anchor_x_var = tk.StringVar(value="0")
        self.percent_anchor_x_spinbox = ttk.Spinbox(
            anchor_frame,
            increment=0.01,
            from_=0,
            to=1,
            textvariable=self.percent_anchor_x_var,
            command=self.update_percent_anchor_from_spinbox,
            width=10,
        )
        self.percent_anchor_x_spinbox.grid(row=2, column=1, padx=5)

        ttk.Label(anchor_frame, text="锚点 Y(%):").grid(row=3, column=0, sticky=tk.W)
        self.percent_anchor_y_var = tk.StringVar(value="0")
        self.percent_anchor_y_spinbox = ttk.Spinbox(
            anchor_frame,
            increment=0.01,
            from_=0,
            to=1,
            textvariable=self.percent_anchor_y_var,
            command=self.update_percent_anchor_from_spinbox,
            width=10,
        )
        self.percent_anchor_y_spinbox.grid(row=3, column=1, padx=5)

        self.percent_anchor_x_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_percent_anchor_from_spinbox()
        )
        self.percent_anchor_y_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_percent_anchor_from_spinbox()
        )

        # 快速预设
        ttk.Label(anchor_frame, text="快速预设:").grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(10, 0)
        )
        preset_frame = ttk.Frame(anchor_frame)
        preset_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W)

        presets = [
            ("左上", 0, 0),
            ("中上", "w/2", 0),
            ("右上", "w", 0),
            ("左中", 0, "h/2"),
            ("中心", "w/2", "h/2"),
            ("右中", "w", "h/2"),
            ("左下", 0, "h"),
            ("中下", "w/2", "h"),
            ("右下", "w", "h"),
        ]

        for i, (name, x, y) in enumerate(presets):
            btn = ttk.Button(
                preset_frame,
                text=name,
                width=6,
                command=lambda x=x, y=y: self.apply_preset(x, y),
            )
            btn.grid(row=i // 3, column=i % 3, padx=2, pady=2)

        # 参考点控制区
        ref_frame = ttk.LabelFrame(control_frame, text="参考点控制", padding=10)
        ref_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(ref_frame, text="参考点 X:").grid(row=0, column=0, sticky=tk.W)
        self.ref_x_var = tk.StringVar(value="0")
        self.ref_x_spinbox = ttk.Spinbox(
            ref_frame,
            from_=0,
            to=9999,
            textvariable=self.ref_x_var,
            command=self.update_ref_from_spinbox,
            width=10,
        )
        self.ref_x_spinbox.grid(row=0, column=1, padx=5)

        ttk.Label(ref_frame, text="参考点 Y:").grid(row=1, column=0, sticky=tk.W)
        self.ref_y_var = tk.StringVar(value="0")
        self.ref_y_spinbox = ttk.Spinbox(
            ref_frame,
            from_=0,
            to=9999,
            textvariable=self.ref_y_var,
            command=self.update_ref_from_spinbox,
            width=10,
        )
        self.ref_y_spinbox.grid(row=1, column=1, padx=5)

        self.ref_x_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_ref_from_spinbox()
        )
        self.ref_y_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_ref_from_spinbox()
        )

        # 显示控制区
        display_frame = ttk.LabelFrame(control_frame, text="显示选项", padding=10)
        display_frame.pack(fill=tk.X)

        ttk.Checkbutton(
            display_frame, text="显示网格", variable=self.show_grid, command=self.redraw
        ).pack(anchor=tk.W)

        ttk.Label(display_frame, text="网格大小:").pack(anchor=tk.W, pady=(5, 0))
        grid_size_frame = ttk.Frame(display_frame)
        grid_size_frame.pack(fill=tk.X, pady=2)

        ttk.Spinbox(
            grid_size_frame,
            from_=4,
            to=128,
            textvariable=self.grid_size,
            width=8,
            command=self.redraw,
        ).pack(side=tk.LEFT)

        ttk.Label(grid_size_frame, text="像素").pack(side=tk.LEFT, padx=5)

        # 缩放控制
        ttk.Label(display_frame, text="缩放:").pack(anchor=tk.W, pady=(5, 0))
        self.scale_slider = ttk.Scale(
            display_frame, from_=0.1, to=5.0, value=1.0, command=self.on_scale_change
        )
        self.scale_slider.pack(fill=tk.X, pady=2)

        self.scale_label = ttk.Label(display_frame, text="100%")
        self.scale_label.pack()

        # 信息显示区
        info_frame = ttk.LabelFrame(control_frame, text="图像信息", padding=10)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        self.info_text = tk.Text(info_frame, height=8, width=30, font=("Consolas", 9))
        self.info_text.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(
            self.root_window,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
        ).pack(side=tk.BOTTOM, fill=tk.X)

    def open_image(self):
        """打开图像文件"""
        file_path = Path(
            filedialog.askopenfilename(
                title="选择贴图文件",
                filetypes=[
                    ("图像文件", "*.png *.jpg *.jpeg *.bmp *.gif"),
                    ("PNG文件", "*.png"),
                    ("所有文件", "*.*"),
                ],
            )
        )

        if file_path:
            try:
                self.image_path = file_path
                self.image = Image.open(file_path)
                self.original_image = self.image.copy()
                self.scale = 1.0
                self.scale_slider.set(1.0)
                self.scale_label.config(text="100%")

                # 初始化锚点到图像中心
                self.anchor_x = self.image.width // 2
                self.anchor_y = self.image.height // 2
                self.anchor_x_var.set(str(self.anchor_x))
                self.anchor_y_var.set(str(self.anchor_y))
                self.anchor_x_spinbox.config(to=self.image.width)
                self.anchor_y_spinbox.config(to=self.image.height)
                self.percent_anchor_x = 0.5
                self.percent_anchor_y = 0.5
                self.percent_anchor_x_var.set(self.percent_anchor_x)
                self.percent_anchor_y_var.set(self.percent_anchor_y)

                # 重置参考点
                self.ref_x = self.anchor_x
                self.ref_y = self.anchor_y
                self.ref_x_var.set(str(self.ref_x))
                self.ref_y_var.set(str(self.ref_y))
                self.ref_x_spinbox.config(to=self.image.width)
                self.ref_y_spinbox.config(to=self.image.height)

                self.relative_offset_x = self.ref_x - self.anchor_x
                self.relative_offset_y = self.ref_y - self.anchor_y

                self.update_info()
                self.redraw()
                self.status_var.set(f"已加载: {file_path}")

            except Exception as e:
                messagebox.showerror(
                    "错误", f"无法打开图像: {traceback.print_exc()}{e}"
                )

    def update_info(self):
        """更新图像信息"""
        if self.image:
            info = f"""图像尺寸: {self.image.width} x {self.image.height}
文件路径: {self.image_path}
"""

            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, info)

    def get_anchor_preset(self):
        """获取锚点预设描述"""
        w, h = self.image.width, self.image.height

        if self.anchor_x == 0 and self.anchor_y == 0:
            return "左上角"
        elif self.anchor_x == w // 2 and self.anchor_y == 0:
            return "中上"
        elif self.anchor_x == w and self.anchor_y == 0:
            return "右上角"
        elif self.anchor_x == 0 and self.anchor_y == h // 2:
            return "左中"
        elif self.anchor_x == w // 2 and self.anchor_y == h // 2:
            return "中心"
        elif self.anchor_x == w and self.anchor_y == h // 2:
            return "右中"
        elif self.anchor_x == 0 and self.anchor_y == h:
            return "左下角"
        elif self.anchor_x == w // 2 and self.anchor_y == h:
            return "中下"
        elif self.anchor_x == w and self.anchor_y == h:
            return "右下角"
        else:
            return "自定义"

    def redraw(self):
        """重新绘制画布"""
        if not self.image:
            return

        self.canvas.delete("all")

        # 计算缩放后的尺寸
        scaled_width = int(self.image.width * self.scale)
        scaled_height = int(self.image.height * self.scale)

        # 计算居中位置
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 800
            canvas_height = 600

        x_offset = (canvas_width - scaled_width) // 2
        y_offset = (canvas_height - scaled_height) // 2

        # 显示缩放后的图像
        scaled_image = self.image.resize(
            (scaled_width, scaled_height), Image.Resampling.NEAREST
        )
        self.photo = ImageTk.PhotoImage(scaled_image)
        self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.photo)

        # 绘制网格
        if self.show_grid.get():
            grid_size = self.grid_size.get() * self.scale
            for x in range(0, scaled_width, int(grid_size)):
                self.canvas.create_line(
                    x_offset + x,
                    y_offset,
                    x_offset + x,
                    y_offset + scaled_height,
                    fill="#444444",
                    width=1,
                    tags="grid",
                )

            for y in range(0, scaled_height, int(grid_size)):
                self.canvas.create_line(
                    x_offset,
                    y_offset + y,
                    x_offset + scaled_width,
                    y_offset + y,
                    fill="#444444",
                    width=1,
                    tags="grid",
                )

        # 边框
        self.canvas.create_rectangle(
            x_offset,
            y_offset,
            x_offset + scaled_width,
            y_offset + scaled_height,
            outline="#FFFFFF",
            width=2,
            tags="grid",
        )

        # 绘制锚点十字
        anchor_screen_x = x_offset + self.anchor_x * self.scale
        anchor_screen_y = y_offset + self.anchor_y * self.scale

        # 大十字
        self.canvas.create_line(
            anchor_screen_x - 15,
            anchor_screen_y,
            anchor_screen_x + 15,
            anchor_screen_y,
            fill="#ff0000",
            width=2,
            tags="anchor",
        )
        self.canvas.create_line(
            anchor_screen_x,
            anchor_screen_y - 15,
            anchor_screen_x,
            anchor_screen_y + 15,
            fill="#ff0000",
            width=2,
            tags="anchor",
        )

        # 小十字（更精确）
        self.canvas.create_line(
            anchor_screen_x - 5,
            anchor_screen_y,
            anchor_screen_x + 5,
            anchor_screen_y,
            fill="#ffffff",
            width=1,
            tags="anchor",
        )
        self.canvas.create_line(
            anchor_screen_x,
            anchor_screen_y - 5,
            anchor_screen_x,
            anchor_screen_y + 5,
            fill="#ffffff",
            width=1,
            tags="anchor",
        )

        # 中心点
        central_x = x_offset + scaled_width // 2
        central_y = y_offset + scaled_height // 2

        self.canvas.create_oval(
            central_x - 6,
            central_y - 6,
            central_x + 6,
            central_y + 6,
            fill="#1100FF",
            width=2,
            tags="ref",
        )

        ref_screen_x = x_offset + self.ref_x * self.scale
        ref_screen_y = y_offset + self.ref_y * self.scale

        # 绘制参考点
        self.canvas.create_oval(
            ref_screen_x - 6,
            ref_screen_y - 6,
            ref_screen_x + 6,
            ref_screen_y + 6,
            outline="#00ff00",
            width=2,
            tags="ref",
        )

        # 绘制连接线（锚点到参考点）
        self.canvas.create_line(
            anchor_screen_x,
            anchor_screen_y,
            ref_screen_x,
            ref_screen_y,
            fill="#ffff00",
            width=1,
            dash=(4, 2),
            tags="line",
        )

        # 显示坐标文本
        self.canvas.create_text(
            10,
            10,
            anchor=tk.NW,
            text=f"锚点: ({self.anchor_x}, {self.anchor_y})",
            fill="#ffffff",
            font=("Arial", 10, "bold"),
            tags="text",
        )

        self.canvas.create_text(
            10,
            30,
            anchor=tk.NW,
            text=f"锚点(%): ({self.percent_anchor_x}, {self.percent_anchor_y})",
            fill="#ffffff",
            font=("Arial", 10, "bold"),
            tags="text",
        )

        self.canvas.create_text(
            10,
            50,
            anchor=tk.NW,
            text=f"偏移: ({self.relative_offset_x}, {self.relative_offset_y})",
            fill="#ffff00",
            font=("Arial", 10, "bold"),
            tags="text",
        )

    def on_canvas_click(self, event):
        """处理画布点击"""
        if not self.image:
            return

        # 计算图像在画布中的位置
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        scaled_width = int(self.image.width * self.scale)
        scaled_height = int(self.image.height * self.scale)

        x_offset = (canvas_width - scaled_width) // 2
        y_offset = (canvas_height - scaled_height) // 2

        # 转换到图像坐标
        img_x = int((event.x - x_offset) / self.scale)
        img_y = int((event.y - y_offset) / self.scale)

        if 0 <= img_x < self.image.width and 0 <= img_y < self.image.height:
            if event.state & 0x0004:  # Ctrl键
                self.ref_x = img_x
                self.ref_y = img_y
                self.ref_x_var.set(img_x)
                self.ref_y_var.set(img_y)
                self.relative_offset_x = img_x - self.anchor_x
                self.relative_offset_y = img_y - self.anchor_y
            else:
                self.anchor_x = img_x
                self.anchor_y = img_y
                self.anchor_x_var.set(img_x)
                self.anchor_y_var.set(img_y)
                self.percent_anchor_x = round(img_x / self.image.width, 4)
                self.percent_anchor_y = round(1 - img_y / self.image.height, 4)
                self.percent_anchor_x_var.set(self.percent_anchor_x)
                self.percent_anchor_y_var.set(self.percent_anchor_y)
                self.relative_offset_x = self.ref_x - img_x
                self.relative_offset_y = self.ref_y - img_y

            self.update_info()
            self.redraw()

    def on_canvas_drag(self, event):
        """处理画布拖动"""
        self.on_canvas_click(event)

    def on_right_click(self, event):
        """右键菜单"""
        if not self.image:
            return

        # 创建右键菜单
        menu = tk.Menu(self.root_window, tearoff=0)
        menu.add_command(
            label="复制锚点坐标",
            command=lambda: self.copy_to_clipboard(f"{self.anchor_x}, {self.anchor_y}"),
        )
        menu.add_command(
            label="复制锚点坐标(%)",
            command=lambda: self.copy_to_clipboard(
                f"{self.percent_anchor_x}, {self.percent_anchor_y}"
            ),
        )
        menu.add_command(
            label="复制偏移坐标",
            command=lambda: self.copy_to_clipboard(
                f"{self.relative_offset_x}, {self.relative_offset_y}"
            ),
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        self.root_window.clipboard_clear()
        self.root_window.clipboard_append(text)
        self.status_var.set("已复制到剪贴板")

    def on_mousewheel(self, event):
        """鼠标滚轮缩放"""
        if not self.image:
            return

        scale_factor = 1.1
        if event.delta > 0:
            self.scale *= scale_factor
        else:
            self.scale /= scale_factor

        # 限制缩放范围
        self.scale = max(0.1, min(5.0, self.scale))
        self.scale_slider.set(self.scale)
        self.scale_label.config(text=f"{int(self.scale * 100)}%")
        self.redraw()

    def on_scale_change(self, value):
        """滑块缩放改变"""
        self.scale = float(value)
        self.scale_label.config(text=f"{int(self.scale * 100)}%")
        self.redraw()

    def update_anchor_from_spinbox(self):
        """从输入框更新锚点"""

        try:
            clamp_x = U.clamp(int(self.anchor_x_var.get()), 0, self.image.width)
            clamp_y = U.clamp(int(self.anchor_y_var.get()), 0, self.image.height)
            self.anchor_x_var.set(clamp_x)
            self.anchor_y_var.set(clamp_y)
            self.anchor_x = clamp_x
            self.anchor_y = clamp_y
            self.percent_anchor_x = round(clamp_x / self.image.width, 4)
            self.percent_anchor_y = round(1 - clamp_y / self.image.height, 4)
            self.percent_anchor_x_var.set(self.percent_anchor_x)
            self.percent_anchor_y_var.set(self.percent_anchor_y)
            self.relative_offset_x = self.ref_x - clamp_x
            self.relative_offset_y = self.ref_y - clamp_y
            self.update_info()
            self.redraw()
        except ValueError:
            traceback.print_exc()

    def update_percent_anchor_from_spinbox(self):
        """从输入框更新锚点"""
        try:
            clamp_x = U.clamp(
                round(float(self.percent_anchor_x_var.get()), 4),
                0,
                1,
            )
            clamp_y = U.clamp(
                round(float(self.percent_anchor_y_var.get()), 4),
                0,
                1,
            )
            self.percent_anchor_x_var.set(clamp_x)
            self.percent_anchor_y_var.set(clamp_y)
            x = round(self.image.width * clamp_x)
            y = round(self.image.height * clamp_y)
            self.anchor_x = x
            self.anchor_y = y
            self.anchor_x_var.set(x)
            self.anchor_y_var.set(y)
            self.relative_offset_x = self.ref_x - x
            self.relative_offset_y = self.ref_y - y
            self.update_info()
            self.redraw()
        except ValueError:
            traceback.print_exc()

    def update_ref_from_spinbox(self):
        """从输入框更新参考点"""
        try:
            clamp_x = U.clamp(
                int(self.ref_x_var.get()),
                0,
                self.image.width,
            )
            clamp_y = U.clamp(
                int(self.ref_y_var.get()),
                0,
                self.image.height,
            )
            self.ref_x = clamp_x
            self.ref_y = clamp_y
            self.ref_x_var = clamp_x
            self.ref_y_var = clamp_y
            self.relative_offset_x = clamp_x - self.anchor_x
            self.relative_offset_y = clamp_y - self.anchor_y
            self.update_info()
            self.redraw()
        except ValueError:
            traceback.print_exc()

    def apply_preset(self, x_preset, y_preset):
        """应用预设"""
        if not self.image:
            return

        w, h = self.image.width, self.image.height

        # 处理特殊值
        if x_preset == "w":
            x = w
        elif x_preset == "w/2":
            x = w // 2
        else:
            x = int(x_preset)

        if y_preset == "h":
            y = h
        elif y_preset == "h/2":
            y = h // 2
        else:
            y = int(y_preset)

        self.anchor_x = x
        self.anchor_y = y
        self.anchor_x_var.set(x)
        self.anchor_y_var.set(y)
        self.percent_anchor_x = round(x / self.image.width, 4)
        self.percent_anchor_y = round(1 - y / self.image.height, 4)
        self.percent_anchor_x_var.set(self.percent_anchor_x)
        self.percent_anchor_y_var.set(self.percent_anchor_y)
        self.relative_offset_x = self.ref_x - x
        self.relative_offset_y = self.ref_y - y

        self.update_info()
        self.redraw()


def main(root):
    app = MeasureAnchor(root)
