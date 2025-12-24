import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import traceback
from pathlib import Path
import utils as U

CTRL_MASK = 0x0004
SHIFT_MASK = 0x0001


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

        # 矩形
        self.rect_start_x = 0
        self.rect_start_y = 0
        self.rect_finish_x = 0
        self.rect_finish_y = 0

        self.setup_ui()

    def clamp_to_edge(self, x, y):
        clamp_x = U.clamp(
            x,
            0,
            self.image.width,
        )
        clamp_y = U.clamp(
            y,
            0,
            self.image.height,
        )

        return clamp_x, clamp_y

    def set_img_scaled(self):
        self.scaled_width = int(self.image.width * self.scale)
        self.scaled_height = int(self.image.height * self.scale)

    def set_img_central_pos(self):
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width = 800
            canvas_height = 600

        self.img_offset_x = (canvas_width - self.scaled_width) // 2
        self.img_offset_y = (canvas_height - self.scaled_height) // 2

    def calculate_img_pos(self, x, y):
        x_offset = x - self.img_offset_x
        y_offset = y - self.img_offset_y

        img_x, img_y = self.clamp_to_edge(
            int(x_offset / self.scale), int(y_offset / self.scale)
        )

        return img_x, img_y

    def get_percent_anchor(self):
        percent_anchor_x = U.clamp(
            round(float(self.percent_anchor_x_var.get()), 4), 0, 1
        )
        percent_anchor_y = U.clamp(
            round(float(self.percent_anchor_y_var.get()), 4), 0, 1
        )

        return percent_anchor_x, percent_anchor_y

    def set_percent_anchor(self, px=None, py=None):
        self.percent_anchor_x = px
        self.percent_anchor_y = py
        self.percent_anchor_x_var.set(px)
        self.percent_anchor_y_var.set(py)

    def calculate_apply_percent_anchor(self, px=None, py=None):
        anchor_x = round(self.image.width * px)
        anchor_y = round(self.image.height * py)

        return anchor_x, anchor_y

    def calculate_percent_anchor(self, ax=None, ay=None):
        px = round(ax / self.image.width, 4)
        py = round(1 - ay / self.image.height, 4)

        return px, py

    def set_relative_offset(self, ox, oy):
        self.relative_offset_x = ox
        self.relative_offset_y = oy

    def get_anchor(self):
        anchor_x, anchor_y = self.clamp_to_edge(
            int(self.anchor_x_var.get()), int(self.anchor_y_var.get())
        )

        return anchor_x, anchor_y

    def set_anchor(self, ax, ay):
        self.anchor_x = ax
        self.anchor_x_var.set(ax)
        self.anchor_y = ay
        self.anchor_y_var.set(ay)

    def set_ref(self, x, y):
        self.ref_x = x
        self.ref_x_var.set(x)
        self.ref_y = y
        self.ref_y_var.set(y)

    def get_ref(self):
        rx, ry = self.clamp_to_edge(
            int(self.ref_x_var.get()), int(self.ref_y_var.get())
        )

        return rx, ry

    def get_rect_pos(self):
        pass

    def set_rect_start_pos(self, x, y):
        self.rect_start_x = x
        self.rect_start_y = y

    def set_rect_finish_pos(self, x, y):
        self.rect_finish_x = x
        self.rect_finish_y = y

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
        display_frame.pack(fill=tk.X, pady=(0, 10))

        # 使用 grid 布局管理器
        display_frame.grid_columnconfigure(0, weight=1)
        display_frame.grid_columnconfigure(1, weight=1)

        # 第0行：显示网格
        ttk.Checkbutton(
            display_frame, 
            text="显示网格", 
            variable=self.show_grid, 
            command=self.redraw
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
            orient="horizontal"
        )
        self.scale_slider.grid(row=3, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # 第4行：缩放百分比标签
        self.scale_label = ttk.Label(display_frame, text="100%")
        self.scale_label.grid(
            row=4, column=0, columnspan=2, padx=5, pady=(0, 5)
        )

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

                origin_width = img.width
                origin_height = img.height

                alpha = img.getchannel("A")

                # 获取非透明区域的边界框
                bbox = alpha.getbbox()
                if bbox:
                    left, top, right, bottom = bbox

                right = origin_width - right
                bottom = origin_height - bottom

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
                self.set_ref(self.anchor_x, self.anchor_y)
                self.ref_x_spinbox.config(to=self.image.width)
                self.ref_y_spinbox.config(to=self.image.height)
                self.set_relative_offset(
                    self.ref_x - self.anchor_x, self.ref_y - self.anchor_y
                )

                self.redraw()
                self.status_var.set(f"已加载: {file_path}")

            except Exception as e:
                messagebox.showerror(
                    "错误", f"无法打开图像: {traceback.print_exc()}{e}"
                )

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
        self.set_img_scaled()
        self.set_img_central_pos()

        # 显示缩放后的图像
        scaled_image = self.image.resize(
            (self.scaled_width, self.scaled_height), Image.Resampling.NEAREST
        )
        self.photo = ImageTk.PhotoImage(scaled_image)
        self.canvas.create_image(
            self.img_offset_x, self.img_offset_y, anchor=tk.NW, image=self.photo
        )

        # 绘制网格
        if self.show_grid.get():
            grid_size = self.grid_size.get() * self.scale
            for x in range(0, self.scaled_width, int(grid_size)):
                self.canvas.create_line(
                    self.img_offset_x + x,
                    self.img_offset_y,
                    self.img_offset_x + x,
                    self.img_offset_y + self.scaled_height,
                    fill="#444444",
                    width=1,
                    tags="grid",
                )

            for y in range(0, self.scaled_height, int(grid_size)):
                self.canvas.create_line(
                    self.img_offset_x,
                    self.img_offset_y + y,
                    self.img_offset_x + self.scaled_width,
                    self.img_offset_y + y,
                    fill="#444444",
                    width=1,
                    tags="grid",
                )

        # 边框
        self.canvas.create_rectangle(
            self.img_offset_x,
            self.img_offset_y,
            self.img_offset_x + self.scaled_width,
            self.img_offset_y + self.scaled_height,
            outline="#FFFFFF",
            width=2,
            tags="border",
        )

        # 绘制锚点十字
        anchor_screen_x = self.img_offset_x + self.anchor_x * self.scale
        anchor_screen_y = self.img_offset_y + self.anchor_y * self.scale

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
        central_x = self.img_offset_x + self.scaled_width // 2
        central_y = self.img_offset_y + self.scaled_height // 2

        self.canvas.create_oval(
            central_x - 4,
            central_y - 4,
            central_x + 4,
            central_y + 4,
            outline="#1100FF",
            width=2,
            tags="central",
        )

        ref_screen_x = self.img_offset_x + self.ref_x * self.scale
        ref_screen_y = self.img_offset_y + self.ref_y * self.scale

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

        screen_rect_start_x = self.img_offset_x + self.rect_start_x * self.scale
        screen_rect_start_y = self.img_offset_y + self.rect_start_y * self.scale
        screen_rect_finish_x = self.img_offset_x + self.rect_finish_x * self.scale
        screen_rect_finish_y = self.img_offset_y + self.rect_finish_y * self.scale

        # 矩形
        self.canvas.create_rectangle(
            screen_rect_start_x,
            screen_rect_start_y,
            screen_rect_finish_x,
            screen_rect_finish_y,
            outline="blue",
            width=2,
            tags="rect",
        )

    def on_canvas_click(self, event):
        """处理画布点击"""
        if not self.image or event.state & SHIFT_MASK:
            return

        self.set_img_scaled()
        self.set_img_central_pos()

        # 转换到图像坐标
        img_x, img_y = self.calculate_img_pos(event.x, event.y)

        if event.state & CTRL_MASK:
            self.set_ref(img_x, img_y)
            self.set_relative_offset(img_x - self.anchor_x, img_y - self.anchor_y)
        else:
            self.set_anchor(img_x, img_y)
            px, py = self.calculate_percent_anchor(img_x, img_y)
            self.set_percent_anchor(px, py)
            self.set_relative_offset(self.ref_x - img_x, self.ref_y - img_y)

        self.redraw()

    def on_canvas_drag(self, event):
        """处理画布拖动"""
        self.on_canvas_click(event)

    def on_shift_drag(self, event):
        if self.image:
            x, y = self.calculate_img_pos(event.x, event.y)
            self.set_rect_finish_pos(x, y)

            self.redraw()

    def on_shift_press(self, event):
        if self.image:
            x, y = self.calculate_img_pos(event.x, event.y)
            self.set_rect_start_pos(x, y)

            self.redraw()

    def on_shift_release(self, event):
        if self.image:
            x, y = self.calculate_img_pos(event.x, event.y)
            self.set_rect_finish_pos(x, y)

            self.redraw()

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
        if self.image:
            ax, ay = self.get_anchor()
            self.set_anchor(ax, ay)
            px, py = self.calculate_percent_anchor(ax, ay)
            self.set_percent_anchor(px, py)
            self.set_relative_offset(self.ref_x - ax, self.ref_y - ay)

            self.redraw()

    def update_percent_anchor_from_spinbox(self):
        """从输入框更新锚点"""
        if self.image:
            px, py = self.get_percent_anchor()
            self.set_percent_anchor(px, py)
            ax, ay = self.calculate_apply_percent_anchor(px, py)
            self.set_anchor(ax, ay)
            self.set_relative_offset(self.ref_x - ax, self.ref_y - ay)

            self.redraw()

    def update_ref_from_spinbox(self):
        """从输入框更新参考点"""
        if self.image:
            rx, ry = self.get_ref()
            self.set_ref(rx, ry)
            self.set_relative_offset(rx - self.anchor_x, ry - self.anchor_y)

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
        self.set_relative_offset(self.ref_x - x, self.ref_y - y)

        self.redraw()


def main(root):
    app = MeasureAnchor(root)
