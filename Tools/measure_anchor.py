import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import traceback, config
from pathlib import Path
from utils import clamp, Vector, Rectangle


CTRL_MASK = 0x0004
SHIFT_MASK = 0x0001

setting = config.setting["measure_anchor"]


class MeasureAnchor:
    def __init__(self, root):
        self.root_window = tk.Toplevel(root)
        self.root_window.title("锚点测量工具")
        self.root_window.geometry("1200x900")

        self.image_path = None
        self.image = None
        self.photo = None
        self.scale = 1.0

        self.img_offset = Vector(0, 0, type=int)

        # 锚点坐标（相对于图像左上角）
        self.anchor = Vector(0, 0, type=int)
        self.percent_anchor = Vector(0.5, 0.5)

        # 参考点坐标
        self.ref_pos = Vector(0, 0, type=int)

        # 相对偏移
        self.relative_offset = Vector(0, 0, type=int)
        self.relative_rect_offset = Rectangle(0, 0, 0, 0, type=int)

        # 网格设置
        self.show_grid = tk.BooleanVar(value=True)
        self.grid_size = tk.IntVar(value=32)

        # 矩形
        self.rect = Rectangle(0, 0, 0, 0, type=int)

        self.setup_ui()

    def clamp_to_edge(self, x, y):
        clamp_x = clamp(x, 0, self.image.width)
        clamp_y = clamp(y, 0, self.image.height)
        return clamp_x, clamp_y

    def get_img_scaled(self):
        self.scaled_width = int(self.image.width * self.scale)
        self.scaled_height = int(self.image.height * self.scale)

    def set_img_central_pos(self):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 800
            canvas_height = 600

        self.img_offset.x = (canvas_width - self.scaled_width) // 2
        self.img_offset.y = (canvas_height - self.scaled_height) // 2

    def calculate_img_pos(self, x, y):
        x_offset = x - self.img_offset.x
        y_offset = y - self.img_offset.y

        img_x, img_y = self.clamp_to_edge(
            int(x_offset / self.scale), int(y_offset / self.scale)
        )

        return img_x, img_y

    def get_percent_anchor_var(self):
        percent_anchor_x = clamp(round(float(self.percent_anchor_x_var.get()), 4), 0, 1)
        percent_anchor_y = clamp(round(float(self.percent_anchor_y_var.get()), 4), 0, 1)

        return percent_anchor_x, percent_anchor_y

    def set_percent_anchor(self, x, y):
        self.percent_anchor.x = x
        self.percent_anchor.y = y
        self.percent_anchor_x_var.set(x)
        self.percent_anchor_y_var.set(y)

    def calculate_apply_percent_anchor(self, px, py):
        anchor_x = round(self.image.width * px)
        anchor_y = round(self.image.height * (1 - py))

        return anchor_x, anchor_y

    def calculate_percent_anchor(self, ax, ay):
        px = round(ax / self.image.width, 4)
        py = round(1 - ay / self.image.height, 4)

        return px, py

    def set_relative_offset(self, x, y):
        self.relative_offset.x = x
        self.relative_offset.y = y

    def get_anchor_var(self):
        anchor_x, anchor_y = self.clamp_to_edge(
            int(self.anchor_x_var.get()), int(self.anchor_y_var.get())
        )

        return anchor_x, anchor_y

    def set_anchor(self, x, y):
        self.anchor.x = x
        self.anchor.y = y
        self.anchor_x_var.set(x)
        self.anchor_y_var.set(y)

    def set_ref(self, x, y):
        self.ref_pos.x = x
        self.ref_pos.y = y
        self.ref_x_var.set(x)
        self.ref_y_var.set(y)

    def get_ref_var(self):
        rx, ry = self.clamp_to_edge(
            int(self.ref_x_var.get()), int(self.ref_y_var.get())
        )

        return rx, ry

    def get_rect_pos_var(self):
        x, y = self.clamp_to_edge(
            int(self.rect_pos_x_var.get()), int(self.rect_pos_y_var.get())
        )

        return x, y

    def get_rect_size_var(self):
        w, h = self.clamp_to_edge(
            int(self.rect_size_w_var.get()), int(self.rect_size_h_var.get())
        )

        return w, h

    def set_rect_pos(self, x, y):
        self.rect.x = x
        self.rect.y = y
        self.rect_pos_x_var.set(x)
        self.rect_pos_y_var.set(y)

    def set_rect_size(self, w, h):
        self.rect.w = w
        self.rect.h = h
        self.rect_size_w_var.set(w)
        self.rect_size_h_var.set(h)

    def set_relative_rect_pos(self, x, y):
        self.relative_rect_offset.x = x
        self.relative_rect_offset.y = y

    def set_relative_rect_size(self, w, h):
        self.relative_rect_offset.w = w
        self.relative_rect_offset.h = h

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
        self.canvas.bind("<Shift-Button-1>", self.on_shift_press)
        self.canvas.bind("<Shift-B1-Motion>", self.on_shift_drag)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_shift_release)

        # 文件操作区
        ttk.Button(control_frame, text="打开图像", command=self.open_image).pack(
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

        for i, (name, x, y) in enumerate(setting["presets"]):
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

        # 矩形控制区
        rect_frame = ttk.LabelFrame(control_frame, text="矩形选项", padding=10)
        rect_frame.pack(fill=tk.X, pady=(0, 10))

        rect_frame.grid_columnconfigure(0, weight=1)
        rect_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(rect_frame, text="矩形对齐边缘", command=self.rect_alignment).grid(
            row=0, column=0, columnspan=2, pady=(0, 10)
        )

        ttk.Label(rect_frame, text="矩形位置 X:").grid(row=1, column=0, sticky=tk.W)
        self.rect_pos_x_var = tk.StringVar(value="0")
        self.rect_pos_x_spinbox = ttk.Spinbox(
            rect_frame,
            from_=0,
            to=9999,
            textvariable=self.rect_pos_x_var,
            command=self.update_rect_pos_from_spinbox,
            width=10,
        )
        self.rect_pos_x_spinbox.grid(row=1, column=1, padx=5)

        ttk.Label(rect_frame, text="矩形位置 Y:").grid(row=2, column=0, sticky=tk.W)
        self.rect_pos_y_var = tk.StringVar(value="0")
        self.rect_pos_y_spinbox = ttk.Spinbox(
            rect_frame,
            from_=0,
            to=9999,
            textvariable=self.rect_pos_y_var,
            command=self.update_rect_pos_from_spinbox,
            width=10,
        )
        self.rect_pos_y_spinbox.grid(row=2, column=1, padx=5)

        ttk.Label(rect_frame, text="矩形长 W:").grid(row=3, column=0, sticky=tk.W)
        self.rect_size_w_var = tk.StringVar(value="0")
        self.rect_size_w_spinbox = ttk.Spinbox(
            rect_frame,
            from_=0,
            to=9999,
            textvariable=self.rect_size_w_var,
            command=self.update_rect_size_from_spinbox,
            width=10,
        )
        self.rect_size_w_spinbox.grid(row=3, column=1, padx=5)

        ttk.Label(rect_frame, text="矩形高 H:").grid(row=4, column=0, sticky=tk.W)
        self.rect_size_h_var = tk.StringVar(value="0")
        self.rect_size_h_spinbox = ttk.Spinbox(
            rect_frame,
            from_=0,
            to=9999,
            textvariable=self.rect_size_h_var,
            command=self.update_rect_size_from_spinbox,
            width=10,
        )
        self.rect_size_h_spinbox.grid(row=4, column=1, padx=5)

        self.rect_pos_x_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_rect_pos_from_spinbox()
        )
        self.rect_pos_y_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_rect_pos_from_spinbox()
        )
        self.rect_size_w_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_rect_size_from_spinbox()
        )
        self.rect_size_h_spinbox.bind(
            "<KeyRelease>", lambda e: self.update_rect_size_from_spinbox()
        )

        # 显示控制区
        display_frame = ttk.LabelFrame(control_frame, text="显示选项", padding=10)
        display_frame.pack(fill=tk.X, pady=(0, 10))

        # 使用 grid 布局管理器
        display_frame.grid_columnconfigure(0, weight=1)
        display_frame.grid_columnconfigure(1, weight=1)

        # 第0行：显示网格
        ttk.Checkbutton(
            display_frame, text="显示网格", variable=self.show_grid, command=self.redraw
        ).grid(row=0, column=0, sticky="w", padx=5, pady=5)

        # 第0行第1列：网格大小标签
        ttk.Label(display_frame, text="网格大小:").grid(row=0, column=1, padx=5, pady=5)

        # 第1行第1列：网格大小输入框
        grid_size_frame = ttk.Frame(display_frame)
        grid_size_frame.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Spinbox(
            grid_size_frame,
            from_=4,
            to=128,
            textvariable=self.grid_size,
            width=8,
            command=self.redraw,
        ).pack(side=tk.LEFT)

        ttk.Label(grid_size_frame, text="像素").pack(side=tk.LEFT, padx=5)

        # 第2行：缩放标签（跨两列）
        ttk.Label(display_frame, text="缩放:").grid(
            row=2, column=0, columnspan=2, padx=5, pady=(10, 0)
        )

        # 第3行：缩放滑块（跨两列并填充宽度）
        self.scale_slider = ttk.Scale(
            display_frame,
            from_=0.05,
            to=5.0,
            value=1.0,
            command=self.on_scale_change,
            orient="horizontal",
        )
        self.scale_slider.grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5
        )

        # 第4行：缩放百分比标签
        self.scale_label = ttk.Label(display_frame, text="100%")
        self.scale_label.grid(row=4, column=0, columnspan=2, padx=5, pady=(0, 5))

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
                title="选择图像文件",
                filetypes=[
                    ("图像文件", "*.png *.jpg *.jpeg *.bmp *.gif"),
                    ("PNG文件", "*.png"),
                    ("所有文件", "*.*"),
                ],
            )
        )

        if file_path.stem:
            try:
                self.image_path = file_path
                self.image = Image.open(file_path)

                img = self.image.copy()
                if self.image.mode == "RGB":
                    img = img.convert("RGBA")

                alpha = img.getchannel("A")

                # 获取非透明区域的边界框
                bbox = alpha.getbbox()
                if bbox:
                    left, top, right, bottom = bbox
                    self.trim = (left, top, right, bottom)

                self.original_image = self.image.copy()
                self.scale = 1.0
                self.scale_slider.set(1.0)
                self.scale_label.config(text="100%")

                # 初始化锚点到图像中心
                self.set_anchor(self.image.width // 2, self.image.height // 2)
                self.anchor_x_spinbox.config(to=self.image.width)
                self.anchor_y_spinbox.config(to=self.image.height)
                self.set_percent_anchor(0.5, 0.5)

                # 重置参考点
                self.set_ref(self.anchor.x, self.anchor.y)
                self.ref_x_spinbox.config(to=self.image.width)
                self.ref_y_spinbox.config(to=self.image.height)
                self.set_relative_offset(
                    self.ref_pos.x - self.anchor.x, self.ref_pos.y - self.anchor.y
                )

                # 重置矩形
                self.rect = Rectangle(0, 0, 0, 0, type=int)
                self.relative_rect_offset = Rectangle(
                    -self.anchor.x,
                    -self.anchor.y,
                    -self.anchor.x,
                    -self.anchor.y,
                    type=int,
                )

                self.redraw()
                self.status_var.set(f"已加载: {file_path}")

            except Exception as e:
                messagebox.showerror(
                    "错误", f"无法打开图像: {traceback.print_exc()}{e}"
                )

    def redraw(self):
        """重新绘制画布"""
        if not self.image:
            return

        self.canvas.delete("all")

        # 计算缩放后的尺寸
        self.get_img_scaled()
        self.set_img_central_pos()

        # 显示缩放后的图像
        scaled_image = self.image.resize(
            (self.scaled_width, self.scaled_height), Image.Resampling.NEAREST
        )
        self.photo = ImageTk.PhotoImage(scaled_image)
        self.canvas.create_image(
            self.img_offset.x, self.img_offset.y, anchor=tk.NW, image=self.photo
        )

        # 绘制网格
        if self.show_grid.get():
            grid_size = self.grid_size.get() * self.scale
            for x in range(0, self.scaled_width, int(grid_size)):
                self.canvas.create_line(
                    self.img_offset.x + x,
                    self.img_offset.y,
                    self.img_offset.x + x,
                    self.img_offset.y + self.scaled_height,
                    fill="#444444",
                    width=1,
                    tags="grid",
                )

            for y in range(0, self.scaled_height, int(grid_size)):
                self.canvas.create_line(
                    self.img_offset.x,
                    self.img_offset.y + y,
                    self.img_offset.x + self.scaled_width,
                    self.img_offset.y + y,
                    fill="#444444",
                    width=1,
                    tags="grid",
                )

        # 边框
        self.canvas.create_rectangle(
            self.img_offset.x,
            self.img_offset.y,
            self.img_offset.x + self.scaled_width,
            self.img_offset.y + self.scaled_height,
            outline="#FFFFFF",
            width=2,
            tags="border",
        )

        screen_rect = Rectangle(
            self.img_offset.x + self.rect.x * self.scale,
            self.img_offset.y + self.rect.y * self.scale,
            self.img_offset.x + self.rect.w * self.scale,
            self.img_offset.y + self.rect.h * self.scale,
            type=int,
        )

        # 矩形
        self.canvas.create_rectangle(
            screen_rect.x,
            screen_rect.y,
            screen_rect.w,
            screen_rect.h,
            outline="blue",
            width=2,
            tags="rect",
        )

        # 绘制锚点十字
        anchor_screen_x = self.img_offset.x + self.anchor.x * self.scale
        anchor_screen_y = self.img_offset.y + self.anchor.y * self.scale

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
        central_x = self.img_offset.x + self.scaled_width // 2
        central_y = self.img_offset.y + self.scaled_height // 2

        self.canvas.create_oval(
            central_x - 4,
            central_y - 4,
            central_x + 4,
            central_y + 4,
            outline="#1100FF",
            width=2,
            tags="central",
        )

        ref_screen_x = self.img_offset.x + self.ref_pos.x * self.scale
        ref_screen_y = self.img_offset.y + self.ref_pos.y * self.scale

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
        texts = [
            (f"图像大小: ({self.image.width}, {self.image.height})", "#ffffff"),
            (f"锚点: ({self.anchor.x}, {self.anchor.y})", "#ffffff"),
            (f"锚点(%): ({self.percent_anchor.x}, {self.percent_anchor.y})", "#ffffff"),
            (f"偏移: ({self.relative_offset.x}, {self.relative_offset.y})", "#ffff00"),
            (
                f"矩形偏移: ({self.relative_rect_offset.x}, {self.relative_rect_offset.y}, {self.relative_rect_offset.w}, {self.relative_rect_offset.h})",
                "#ffff00",
            ),
        ]
        for i, (t, c) in enumerate(texts):
            self.canvas.create_text(
                10,
                10 + 20 * i,
                anchor=tk.NW,
                text=t,
                fill=c,
                font=("Arial", 10, "bold"),
                tags="text",
            )

    def on_canvas_click(self, event):
        """处理画布点击"""
        if not self.image or event.state & SHIFT_MASK:
            return

        self.get_img_scaled()
        self.set_img_central_pos()

        # 转换到图像坐标
        img_x, img_y = self.calculate_img_pos(event.x, event.y)

        if event.state & CTRL_MASK:
            self.set_ref(img_x, img_y)
            self.set_relative_offset(img_x - self.anchor.x, img_y - self.anchor.y)
        else:
            self.set_anchor(img_x, img_y)
            px, py = self.calculate_percent_anchor(img_x, img_y)
            self.set_percent_anchor(px, py)
            self.set_relative_offset(self.ref_pos.x - img_x, self.ref_pos.y - img_y)
            self.set_relative_rect_pos(
                self.rect.x - img_x,
                self.rect.y - img_y,
            )
            self.set_relative_rect_size(
                self.rect.w - img_x,
                self.rect.h - img_y,
            )

        self.redraw()

    def on_canvas_drag(self, event):
        """处理画布拖动"""
        self.on_canvas_click(event)

    def on_shift_drag(self, event):
        if self.image:
            x, y = self.calculate_img_pos(event.x, event.y)
            self.set_rect_size(x, y)
            self.set_relative_rect_size(x - self.anchor.x, y - self.anchor.y)
            self.redraw()

    def on_shift_press(self, event):
        if self.image:
            x, y = self.calculate_img_pos(event.x, event.y)
            self.set_rect_pos(x, y)
            self.set_relative_rect_pos(x - self.anchor.x, y - self.anchor.y)
            self.set_relative_rect_size(x - self.anchor.x, y - self.anchor.y)
            self.redraw()

    def on_shift_release(self, event):
        if self.image:
            x, y = self.calculate_img_pos(event.x, event.y)
            self.set_rect_size(x, y)
            self.set_relative_rect_size(x - self.anchor.x, y - self.anchor.y)
            self.redraw()

    def on_right_click(self, event):
        """右键菜单"""
        if not self.image:
            return

        # 创建右键菜单
        menu = tk.Menu(self.root_window, tearoff=0)
        menu.add_command(
            label="复制图像大小",
            command=lambda: self.copy_to_clipboard(
                f"{self.image.width}, {self.image.height}"
            ),
        )
        menu.add_command(
            label="复制锚点坐标",
            command=lambda: self.copy_to_clipboard(f"{self.anchor.x}, {self.anchor.y}"),
        )
        menu.add_command(
            label="复制锚点坐标(%)",
            command=lambda: self.copy_to_clipboard(
                f"{self.percent_anchor.x}, {self.percent_anchor.y}"
            ),
        )
        menu.add_command(
            label="复制偏移坐标",
            command=lambda: self.copy_to_clipboard(
                f"{self.relative_offset.x}, {self.relative_offset.y}"
            ),
        )
        menu.add_command(
            label="复制矩形偏移坐标",
            command=lambda: self.copy_to_clipboard(
                f"{self.relative_rect_offset.x}, {self.relative_rect_offset.y}, {self.relative_rect_offset.w}, {self.relative_rect_offset.h}"
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

    def rect_alignment(self):
        if self.image:
            l, t, r, b = self.trim
            self.set_rect_pos(l, t)
            self.set_rect_size(r, b)
            self.set_relative_rect_pos(l - self.anchor.x, t - self.anchor.y)
            self.set_relative_rect_size(r - self.anchor.x, b - self.anchor.y)
            self.redraw()

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
        if self.image:
            ax, ay = self.get_anchor_var()
            self.set_anchor(ax, ay)
            px, py = self.calculate_percent_anchor(ax, ay)
            self.set_percent_anchor(px, py)
            self.set_relative_offset(self.ref_pos.x - ax, self.ref_pos.y - ay)
            self.set_relative_rect_pos(
                self.rect.x - ax,
                self.rect.y - ay,
            )
            self.set_relative_rect_size(
                self.rect.w - ax,
                self.rect.h - ay,
            )
            self.redraw()

    def update_percent_anchor_from_spinbox(self):
        """从输入框更新锚点"""
        if self.image:
            px, py = self.get_percent_anchor_var()
            self.set_percent_anchor(px, py)
            ax, ay = self.calculate_apply_percent_anchor(px, py)
            self.set_anchor(ax, ay)
            self.set_relative_offset(self.ref_pos.x - ax, self.ref_pos.y - ay)
            self.set_relative_rect_pos(self.rect.x - ax, self.rect.y - ay)
            self.set_relative_rect_size(self.rect.w - ax, self.rect.h - ay)
            self.redraw()

    def update_ref_from_spinbox(self):
        """从输入框更新参考点"""
        if self.image:
            rx, ry = self.get_ref_var()
            self.set_ref(rx, ry)
            self.set_relative_offset(rx - self.anchor.x, ry - self.anchor.y)
            self.redraw()

    def update_rect_pos_from_spinbox(self):
        x, y = self.get_rect_pos_var()
        self.set_rect_pos(x, y)
        self.set_relative_rect_pos(x - self.anchor.x, y - self.anchor.y)
        self.redraw()

    def update_rect_size_from_spinbox(self):
        w, h = self.get_rect_size_var()
        self.set_rect_size(w, h)
        self.set_relative_rect_pos(w - self.anchor.x, h - self.anchor.y)
        self.redraw()

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

        self.set_anchor(x, y)
        px, py = self.calculate_percent_anchor(x, y)
        self.set_percent_anchor(px, py)
        self.set_relative_offset(self.ref_pos.x - x, self.ref_pos.y - y)
        self.set_relative_rect_pos(
            self.rect.x - x,
            self.rect.y - y,
        )
        self.set_relative_rect_size(
            self.rect.w - x,
            self.rect.h - y,
        )
        self.redraw()


def main(root):
    app = MeasureAnchor(root)
