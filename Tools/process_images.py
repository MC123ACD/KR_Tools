import traceback, config
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import tkinter as tk
from tkinter import ttk
from utils import run_texconv


settings = config.setting["process_images"]


class ImageProcessorGUI:
    def __init__(self, root):
        self.root = tk.Toplevel(root)
        self.root.title("图片处理工具")
        self.root.geometry("600x500")

        self.create_interface()
        self.setup_styles()

    def create_interface(self):
        """创建整个界面"""
        # 图片处理选项部分
        self.create_process_options_section()

        # 输出设置部分
        self.create_output_options_section()

        # 控制按钮部分
        self.create_control_buttons_section()

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(5, weight=1)

    def create_process_options_section(self):
        """创建图片处理选项部分"""
        # 创建框架
        self.process_frame = ttk.LabelFrame(self.root, text="图片处理选项", padding=10)
        self.process_frame.grid(
            row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )

        # 裁剪选项
        self.trim_var = tk.BooleanVar(value=settings["use_trim"])
        self.trim_check = ttk.Checkbutton(
            self.process_frame, text="裁剪透明边", variable=self.trim_var
        )
        self.trim_check.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        self.create_resize_section()
        self.create_sharpen_section()
        self.create_brightness_section()
        self.create_mirror_section()

        # 配置处理框架的列权重
        self.process_frame.columnconfigure(3, weight=1)

    def create_resize_section(self):
        """创建缩放设置部分"""
        self.size_label = ttk.Label(self.process_frame, text="缩放设置:")
        self.size_label.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="w")

        self.use_percent_size_var = tk.BooleanVar(value=settings["use_percent_size"])
        self.use_percent_size = ttk.Checkbutton(
            self.process_frame,
            text="是否百分比缩放",
            variable=self.use_percent_size_var,
        )
        self.use_percent_size.grid(
            row=2, column=0, columnspan=4, padx=5, pady=2, sticky="w"
        )

        self.size_x_label = ttk.Label(self.process_frame, text="宽度:")
        self.size_x_label.grid(row=3, column=0, padx=5, pady=2, sticky="w")

        self.size_x_var = tk.StringVar(value=settings["size_x"])
        self.size_x_entry = ttk.Entry(
            self.process_frame, textvariable=self.size_x_var, width=10
        )
        self.size_x_entry.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        self.size_y_label = ttk.Label(self.process_frame, text="高度:")
        self.size_y_label.grid(row=3, column=2, padx=20, pady=2, sticky="w")

        self.size_y_var = tk.StringVar(value=settings["size_y"])
        self.size_y_entry = ttk.Entry(
            self.process_frame, textvariable=self.size_y_var, width=10
        )
        self.size_y_entry.grid(row=3, column=3, padx=5, pady=2, sticky="w")

    def create_sharpen_section(self):
        """创建锐化设置部分"""
        self.sharp_label = ttk.Label(self.process_frame, text="锐化设置:")
        self.sharp_label.grid(row=4, column=0, columnspan=4, padx=5, pady=5, sticky="w")

        self.sharp_percent_label = ttk.Label(self.process_frame, text="强度:")
        self.sharp_percent_label.grid(row=5, column=0, padx=5, pady=2, sticky="w")

        self.sharp_percent_var = tk.StringVar(value=settings["sharpen_percent"])
        self.sharp_percent_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_percent_var, width=10
        )
        self.sharp_percent_entry.grid(row=5, column=1, padx=5, pady=2, sticky="w")

        self.sharp_radius_label = ttk.Label(self.process_frame, text="半径:")
        self.sharp_radius_label.grid(row=5, column=2, padx=20, pady=2, sticky="w")

        self.sharp_radius_var = tk.StringVar(value=settings["sharpen_radius"])
        self.sharp_radius_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_radius_var, width=10
        )
        self.sharp_radius_entry.grid(row=5, column=3, padx=5, pady=2, sticky="w")

        self.sharp_threshold_label = ttk.Label(self.process_frame, text="阈值:")
        self.sharp_threshold_label.grid(row=6, column=0, padx=5, pady=2, sticky="w")

        self.sharp_threshold_var = tk.StringVar(value=settings["sharpen_threshold"])
        self.sharp_threshold_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_threshold_var, width=10
        )
        self.sharp_threshold_entry.grid(row=6, column=1, padx=5, pady=2, sticky="w")

    def create_brightness_section(self):
        """创建亮度设置部分"""
        self.brightness_label = ttk.Label(self.process_frame, text="亮度:")
        self.brightness_label.grid(row=7, column=0, padx=5, pady=5, sticky="w")

        self.brightness_var = tk.StringVar(value=settings["brightness"])
        self.brightness_entry = ttk.Entry(
            self.process_frame, textvariable=self.brightness_var, width=10
        )
        self.brightness_entry.grid(row=7, column=1, padx=5, pady=5, sticky="w")

    def create_mirror_section(self):
        """创建镜像设置部分"""
        self.mirror_label = ttk.Label(self.process_frame, text="镜像设置:")
        self.mirror_label.grid(
            row=8, column=0, columnspan=4, padx=5, pady=5, sticky="w"
        )

        # 水平镜像
        self.mirror_horizontal_var = tk.BooleanVar(value=settings["mirror_horizontal"])
        self.mirror_horizontal_check = ttk.Checkbutton(
            self.process_frame, text="水平镜像", variable=self.mirror_horizontal_var
        )
        self.mirror_horizontal_check.grid(row=9, column=0, padx=5, pady=2, sticky="w")

        # 垂直镜像
        self.mirror_vertical_var = tk.BooleanVar(value=settings["mirror_vertical"])
        self.mirror_vertical_check = ttk.Checkbutton(
            self.process_frame, text="垂直镜像", variable=self.mirror_vertical_var
        )
        self.mirror_vertical_check.grid(row=9, column=1, padx=20, pady=2, sticky="w")

    def create_output_options_section(self):
        """创建输出设置部分"""
        # 创建框架
        self.output_format_frame = ttk.LabelFrame(
            self.root, text="输出设置", padding=10
        )
        self.output_format_frame.grid(
            row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )

        # 输出格式
        self.output_format_label = ttk.Label(self.output_format_frame, text="输出格式:")
        self.output_format_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.output_format_var = tk.StringVar(value=settings["output_format"])
        self.output_format_combo = ttk.Combobox(
            self.output_format_frame,
            textvariable=self.output_format_var,
            values=["png", "bc3", "bc7"],
            state="readonly",
            width=10,
        )
        self.output_format_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 删除临时PNG选项
        self.delete_png_var = tk.StringVar(value=settings["delete_temporary_png"])
        self.delete_png_check = ttk.Checkbutton(
            self.output_format_frame,
            text="删除临时PNG文件",
            variable=self.delete_png_var,
        )
        self.delete_png_check.grid(row=0, column=2, padx=20, pady=5, sticky="w")

    def create_control_buttons_section(self):
        """创建控制按钮部分"""
        # 创建框架
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

        # 开始处理按钮
        self.process_btn = ttk.Button(
            self.control_frame,
            text="开始处理",
            command=self.start_processing,
            style="Accent.TButton",
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

    def setup_styles(self):
        """设置控件样式"""
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 10, "bold"))

    def start_processing(self):
        """开始处理图片"""
        self.process_images()

    def process_images(self):
        """处理所有图片"""
        input_subdir = self.get_input_files()

        # 处理所有图片
        for dir_name, (dir_list) in input_subdir.items():
            for filename, img in dir_list:
                self.process_img(
                    filename,
                    img,
                    dir_name if dir_name != "imgs" else None,
                )

        print("\n✅ 所有图片处理完成！")

    def get_input_files(self):
        """获取输入文件"""
        input_subdir = {"imgs": []}

        for item in config.input_path.iterdir():
            print(f"📖 读取: {item.name}")

            if item.is_dir():
                input_subdir[item.name] = []

                for file in item.iterdir():
                    new_img = self.load_image(file)
                    input_subdir[item.name].append((file.name, new_img))

            elif item.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                new_img = self.load_image(item)
                input_subdir["imgs"].append((item.name, new_img))

        return input_subdir

    def load_image(self, file):
        """加载图片"""
        with Image.open(file) as img:
            new_img = img.copy()

            if self.trim_var.get():
                if new_img.mode == "RGB":
                    img = img.convert("RGBA")

                # 获取Alpha通道
                alpha = img.getchannel("A")

                # 裁剪图片
                bbox = alpha.getbbox()
                if bbox:
                    new_img = img.crop(bbox)
                    print(
                        f"📖 加载图片  {file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                    )
                else:
                    print(f"📖 加载图片  {file.name} ({img.width}x{img.height})")
            else:
                print(f"📖 加载图片  {file.name} ({img.width}x{img.height})")

        return new_img

    def set_img_size(self, img):
        """设置图片尺寸"""
        w, h = int(self.size_x_var.get()), int(self.size_y_var.get())

        use_percent_size = self.use_percent_size_var.get()

        if use_percent_size:
            w /= 100
            h /= 100

        width, height = img.size
        new_width = round(width * w)
        new_height = round(height * h)

        print(f"🔎 缩放图片大小，从{width}x{height}到{new_width}x{new_height}")

        return img.resize((new_width, new_height))

    def set_img_sharpen(self, img):
        """锐化图片"""
        percent = int(self.sharp_percent_var.get())
        radius = int(self.sharp_radius_var.get())
        threshold = int(self.sharp_threshold_var.get())

        if not (percent and percent and threshold):
            return img

        sharpened = img.filter(ImageFilter.UnsharpMask(radius, percent, threshold))
        print(f"🔼 锐化图片，强度{percent}%，半径{radius}，阈值{threshold}")

        return sharpened

    def set_img_brightness(self, img):
        """调整图片亮度"""
        brightness_factor = float(self.brightness_var.get())

        if brightness_factor == 1:
            return img

        enhancer = ImageEnhance.Brightness(img)
        compensated = enhancer.enhance(brightness_factor)
        print(f"🔆 修改图片亮度为{brightness_factor}倍")

        return compensated

    def set_img_mirror(self, img):
        """镜像图片"""
        mirror_horizontal = self.mirror_horizontal_var.get()
        mirror_vertical = self.mirror_vertical_var.get()

        if not (mirror_horizontal or mirror_vertical):
            return img

        if mirror_horizontal:
            # 水平镜像
            mirrored_img = img.transpose(Image.FLIP_LEFT_RIGHT)
            print(f"🔄 水平镜像图片")

        if mirror_vertical:
            # 垂直镜像
            mirrored_img = img.transpose(Image.FLIP_TOP_BOTTOM)
            print(f"🔄 垂直镜像图片")

        return mirrored_img

    def process_img(self, name, img, in_dir):
        """处理单个图片"""
        output_img = None

        # 应用各项处理
        img = self.set_img_size(img)
        img = self.set_img_sharpen(img)
        img = self.set_img_brightness(img)
        img = self.set_img_mirror(img)

        # 确定输出路径
        if in_dir:
            output_dir = config.output_path / in_dir
            output_dir.mkdir(exist_ok=True)
            output_img = output_dir / name
        else:
            output_img = config.output_path / name

        # 保存图片
        output_format = self.output_format_var.get()

        if output_format == "png":
            img.save(output_img)
            print(f"✅ 保存为PNG: {name}")
        elif output_format in ["bc3", "bc7"]:
            # 先保存为PNG临时文件
            temp_png = output_img.with_suffix(".png")
            img.save(temp_png)
            self.save_to_dds(temp_png, int(output_format[-1]))
        else:
            img.save(output_img)
            print(f"🖼️ 保存图片: {name}")

    def save_to_dds(self, output_file, bc):
        """将PNG图片转换为DDS格式"""
        print(f"✅ 转换为DDS BC{bc}格式: {output_file.name}...")

        output_format = f"BC{bc}_UNORM"

        # 使用texconv工具进行格式转换
        run_texconv(output_format, output_file, config.output_path)

        print(f"✅ DDS转换成功: {output_file.stem}.dds")

        # 删除临时PNG文件
        if self.delete_png_var.get():
            Path(output_file).unlink()
            print(f"🗑️  已删除临时PNG文件: {output_file.name}")


def main(root):
    app = ImageProcessorGUI(root)
