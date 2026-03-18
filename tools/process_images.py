import traceback
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import tkinter as tk
from tkinter import ttk
import lib.config as config
from lib.utils import save_to_dds, run_app
from lib.classes import Size
import lib.log as log

log = log.setup_logging()


class ImageProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("图片处理工具")
        self.root.geometry("600x600")

        self.create_interface()

    def create_interface(self):
        """创建整个界面"""
        # 图片处理选项部分
        self.create_process_options_section()

        # 输出设置部分
        self.create_output_options_section()

        self.create_merge_section()

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
        self.trim_var = tk.BooleanVar(value=setting["use_trim"])
        self.trim_check = ttk.Checkbutton(
            self.process_frame, text="裁剪透明边", variable=self.trim_var
        )
        self.trim_check.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        self.preset_four_btn = ttk.Button(
            self.process_frame,
            text="五代缩放三代预设",
            command=lambda: self.apply_preset(setting["presets"]["five"]),
            width=16,
        )
        self.preset_four_btn.grid(row=0, column=1, padx=12, pady=2)

        self.preset_reset = ttk.Button(
            self.process_frame,
            text="重置",
            command=lambda: self.apply_preset(setting),
            width=8,
        )
        self.preset_reset.grid(row=0, column=2, padx=8, pady=2)

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

        self.use_percent_size_var = tk.BooleanVar(value=setting["use_percent_size"])
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

        self.size_x_var = tk.IntVar(value=setting["size_x"])
        self.size_x_entry = ttk.Entry(
            self.process_frame, textvariable=self.size_x_var, width=10
        )
        self.size_x_entry.grid(row=3, column=1, padx=5, pady=2, sticky="w")

        self.size_y_label = ttk.Label(self.process_frame, text="高度:")
        self.size_y_label.grid(row=3, column=2, padx=20, pady=2, sticky="w")

        self.size_y_var = tk.IntVar(value=setting["size_y"])
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

        self.sharp_percent_var = tk.IntVar(value=setting["sharpen_percent"])
        self.sharp_percent_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_percent_var, width=10
        )
        self.sharp_percent_entry.grid(row=5, column=1, padx=5, pady=2, sticky="w")

        self.sharp_radius_label = ttk.Label(self.process_frame, text="半径:")
        self.sharp_radius_label.grid(row=5, column=2, padx=20, pady=2, sticky="w")

        self.sharp_radius_var = tk.IntVar(value=setting["sharpen_radius"])
        self.sharp_radius_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_radius_var, width=10
        )
        self.sharp_radius_entry.grid(row=5, column=3, padx=5, pady=2, sticky="w")

        self.sharp_threshold_label = ttk.Label(self.process_frame, text="阈值:")
        self.sharp_threshold_label.grid(row=6, column=0, padx=5, pady=2, sticky="w")

        self.sharp_threshold_var = tk.IntVar(value=setting["sharpen_threshold"])
        self.sharp_threshold_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_threshold_var, width=10
        )
        self.sharp_threshold_entry.grid(row=6, column=1, padx=5, pady=2, sticky="w")

    def create_brightness_section(self):
        """创建亮度设置部分"""
        self.brightness_label = ttk.Label(self.process_frame, text="亮度:")
        self.brightness_label.grid(row=7, column=0, padx=5, pady=5, sticky="w")

        self.brightness_var = tk.DoubleVar(value=setting["brightness"])
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
        self.mirror_horizontal_var = tk.BooleanVar(value=setting["mirror_horizontal"])
        self.mirror_horizontal_check = ttk.Checkbutton(
            self.process_frame, text="水平镜像", variable=self.mirror_horizontal_var
        )
        self.mirror_horizontal_check.grid(row=9, column=0, padx=5, pady=2, sticky="w")

        # 垂直镜像
        self.mirror_vertical_var = tk.BooleanVar(value=setting["mirror_vertical"])
        self.mirror_vertical_check = ttk.Checkbutton(
            self.process_frame, text="垂直镜像", variable=self.mirror_vertical_var
        )
        self.mirror_vertical_check.grid(row=9, column=1, padx=20, pady=2, sticky="w")

    def create_merge_section(self):
        """创建合并设置部分"""
        self.merge_label = ttk.Label(self.process_frame, text="合并设置:")
        self.merge_label.grid(
            row=10, column=0, columnspan=4, padx=5, pady=5, sticky="w"
        )

        # 启用合并
        self.merge_var = tk.BooleanVar(value=setting["merge_images"])
        self.merge_check = ttk.Checkbutton(
            self.process_frame,
            text="合并每个文件夹中的图像",
            variable=self.merge_var,
        )
        self.merge_check.grid(row=11, column=0, padx=5, pady=2, sticky="w")

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

        self.output_format_var = tk.StringVar(value=setting["output_format"])
        self.output_format_combo = ttk.Combobox(
            self.output_format_frame,
            textvariable=self.output_format_var,
            values=["png", "bc3", "bc7"],
            state="readonly",
            width=10,
        )
        self.output_format_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 删除临时PNG选项
        self.delete_temp_var = tk.BooleanVar(value=setting["delete_temporary_png"])
        self.delete_png_check = ttk.Checkbutton(
            self.output_format_frame,
            text="删除临时PNG文件",
            variable=self.delete_temp_var,
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
            command=self.start_process,
            width=30,
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

    def apply_preset(self, preset):
        """应用预设配置"""
        # 更新界面控件
        self.trim_var.set(preset["use_trim"])
        self.use_percent_size_var.set(preset["use_percent_size"])
        self.size_x_var.set(preset["size_x"])
        self.size_y_var.set(preset["size_y"])
        self.sharp_percent_var.set(preset["sharpen_percent"])
        self.sharp_radius_var.set(preset["sharpen_radius"])
        self.sharp_threshold_var.set(preset["sharpen_threshold"])
        self.brightness_var.set(preset["brightness"])
        self.mirror_horizontal_var.set(preset["mirror_horizontal"])
        self.mirror_vertical_var.set(preset["mirror_vertical"])
        self.merge_var.set(preset["merge_images"])
        self.output_format_var.set(preset["output_format"])
        self.delete_temp_var.set(preset["delete_temporary_png"])

    def get_all_var(self):
        return {
            "trim_var": self.trim_var.get(),
            "use_percent_size_var": self.use_percent_size_var.get(),
            "size_var": Size(self.size_x_var.get(), self.size_y_var.get()),
            "sharp_percent_var": self.sharp_percent_var.get(),
            "sharp_radius_var": self.sharp_radius_var.get(),
            "sharp_threshold_var": self.sharp_threshold_var.get(),
            "brightness_var": self.brightness_var.get(),
            "mirror_horizontal_var": self.mirror_horizontal_var.get(),
            "mirror_vertical_var": self.mirror_vertical_var.get(),
            "merge_var": self.merge_var.get(),
            "output_format_var": self.output_format_var.get(),
            "delete_temp_var": self.delete_temp_var.get(),
        }

    def start_process(self):
        global setting_var
        setting_var = self.get_all_var()

        process_images()


def load_image(file):
    """加载图片"""
    with Image.open(file) as img:
        new_img = img.copy()

    if not setting_var["trim_var"]:
        log.info(f"📖 加载图片  {file.name} ({img.width}x{img.height})")
        return new_img

    # 裁剪图片
    bbox = img.getbbox() or (0, 0, 0, 0)
    new_img = img.crop(bbox)
    log.info(
        f"📖 加载图片  {file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
    )

    return new_img


def get_input_files():
    """获取输入文件"""
    input_subdir = {"imgs": []}

    for item in config.input_path.iterdir():
        log.info(f"📖 读取: {item.name}")

        if item.is_dir():
            input_subdir[item.name] = []

            for file in item.iterdir():
                new_img = load_image(file)
                input_subdir[item.name].append((file.name, new_img))

        elif item.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
            new_img = load_image(item)
            input_subdir["imgs"].append((item.name, new_img))

    for subdir in input_subdir:
        subdir_list = input_subdir[subdir]
        subdir_list.sort(key=lambda x: x[0])

    return input_subdir


def set_img_size(img):
    """设置图片尺寸"""
    size = setting_var["size_var"]
    new_size = Size(size.w, size.h)

    use_percent_size = setting_var["use_percent_size_var"]

    if use_percent_size:
        new_size.w /= 100
        new_size.h /= 100

        if new_size == 1 and new_size == 1:
            return img

    width, height = img.size
    new_width = round(width * new_size.w)
    new_height = round(height * new_size.h)

    img = img.resize((new_width, new_height))
    log.info(f"🔎 缩放图片大小，从{width}x{height}到{new_width}x{new_height}")

    return img


def set_img_sharpen(img):
    """锐化图片"""
    percent = setting_var["sharp_percent_var"]
    radius = setting_var["sharp_radius_var"]
    threshold = setting_var["sharp_threshold_var"]

    if not all([percent, radius, threshold]):
        return img

    sharpened = img.filter(ImageFilter.UnsharpMask(radius, percent, threshold))
    log.info(f"🔼 锐化图片，强度{percent}%，半径{radius}，阈值{threshold}")

    return sharpened


def set_img_brightness(img):
    """调整图片亮度"""
    brightness_factor = setting_var["brightness_var"]

    if brightness_factor == 1:
        return img

    enhancer = ImageEnhance.Brightness(img)
    compensated = enhancer.enhance(brightness_factor)
    log.info(f"🔆 修改图片亮度为{brightness_factor}倍")

    return compensated


def set_img_mirror(img):
    """镜像图片"""
    mirror_horizontal = setting_var["mirror_horizontal_var"]
    mirror_vertical = setting_var["mirror_vertical_var"]

    if not (mirror_horizontal or mirror_vertical):
        return img

    if mirror_horizontal:
        # 水平镜像
        mirrored_img = img.transpose(Image.FLIP_LEFT_RIGHT)
        log.info(f"🔄 水平镜像图片")

    if mirror_vertical:
        # 垂直镜像
        mirrored_img = img.transpose(Image.FLIP_TOP_BOTTOM)
        log.info(f"🔄 垂直镜像图片")

    return mirrored_img


def save_img(img, in_dir, name):
    # 确定输出路径
    if in_dir:
        output_dir = config.output_path / in_dir
        output_dir.mkdir(exist_ok=True)
        output_img = output_dir / name
    else:
        output_img = config.output_path / name

    # 保存图片
    output_format = setting_var["output_format_var"]

    # 先保存为PNG临时文件
    img.save(output_img)

    if output_format == "png":
        log.info(f"✅ 保存为PNG: {name}")
    elif output_format == "bc3" or output_format == "bc7":
        save_to_dds(
            output_img,
            config.output_path,
            output_format,
            setting_var["delete_temp_png"],
        )


def process_img(name, img, in_dir):
    """处理单个图片"""
    # 应用各项处理
    img = set_img_size(img)
    img = set_img_sharpen(img)
    img = set_img_brightness(img)
    img = set_img_mirror(img)

    if setting_var["merge_var"]:
        return

    save_img(img, in_dir, name)


def merge_images(groups):
    # 合并每个文件夹中的图片
    for i in range(len(groups)):
        main_dir_name = list(groups.keys())[i]
        main_dir_list = groups[main_dir_name]

        for j in range(i + 1, len(groups)):
            other_dir_name = list(groups.keys())[j]
            other_dir_list = groups[other_dir_name]

            if len(main_dir_list) != len(other_dir_list):
                log.error(
                    f"⚠️ 无法合并文件夹 {main_dir_name} 和 {other_dir_name}，因为它们的图片数量不一致"
                )
                continue

            for idx in range(len(main_dir_list)):
                main_name, main_img = main_dir_list[idx]
                other_name, other_img = other_dir_list[idx]

                new_img = Image.alpha_composite(main_img, other_img)
                log.info(
                    f"🖼️ 合并图片: {main_dir_name}/{main_name} + {other_dir_name}/{other_name}"
                )

                save_img(new_img, Path("merged"), main_name)


def process_images():
    """处理所有图片"""
    input_subdir = get_input_files()
    groups = {}

    # 处理所有图片
    for dir_name, (dir_list) in input_subdir.items():
        if dir_name != "imgs":
            groups[dir_name] = dir_list

        for filename, img in dir_list:
            process_img(
                filename,
                img,
                dir_name if dir_name != "imgs" else None,
            )

    if setting_var["merge_var"]:
        merge_images(groups)

    log.info("\n✅ 所有图片处理完成！")


def main(root=None):
    global setting
    setting = config.setting["process_images"]
    run_app(root, ImageProcessor)


if __name__ == "__main__":
    main()
