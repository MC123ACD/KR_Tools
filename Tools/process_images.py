import traceback
import subprocess
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading, config
from utils import run_texconv


settings = config.setting["process_images"]


class ImageProcessorGUI:
    def __init__(self, root):
        self.root = tk.Toplevel(root)
        self.root.title("图片处理工具")
        self.root.geometry("600x500")

        self.create_widgets()
        self.setup_layout()

    def create_widgets(self):
        # 图片处理选项
        self.process_frame = ttk.LabelFrame(self.root, text="图片处理选项", padding=10)

        # 裁剪选项
        self.trim_var = tk.BooleanVar(value=settings["use_trim"])
        self.trim_check = ttk.Checkbutton(
            self.process_frame, text="裁剪透明区域", variable=self.trim_var
        )

        # 缩放选项
        self.size_label = ttk.Label(
            self.process_frame, text="缩放设置:"
        )
        self.use_percent_size_var = tk.BooleanVar(value=settings["use_percent_size"])
        self.use_percent_size = ttk.Checkbutton(
            self.process_frame, text="是否百分比缩放", variable=self.use_percent_size_var
        )

        self.size_x_label = ttk.Label(self.process_frame, text="宽度:")
        self.size_x_var = tk.StringVar(value=settings["size_x"])
        self.size_x_entry = ttk.Entry(
            self.process_frame, textvariable=self.size_x_var, width=10
        )
        self.size_y_label = ttk.Label(self.process_frame, text="高度:")
        self.size_y_var = tk.StringVar(value=settings["size_y"])
        self.size_y_entry = ttk.Entry(
            self.process_frame, textvariable=self.size_y_var, width=10
        )

        # 锐化选项
        self.sharp_label = ttk.Label(self.process_frame, text="锐化设置:")
        self.sharp_percent_label = ttk.Label(self.process_frame, text="强度(%):")
        self.sharp_percent_var = tk.StringVar(value=settings["sharpen_percent"])
        self.sharp_percent_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_percent_var, width=10
        )
        self.sharp_radius_label = ttk.Label(self.process_frame, text="半径:")
        self.sharp_radius_var = tk.StringVar(value=settings["sharpen_radius"])
        self.sharp_radius_entry = ttk.Entry(
            self.process_frame, textvariable=self.sharp_radius_var, width=10
        )
        self.sharp_threshold_label = ttk.Label(self.process_frame, text="阈值:")
        self.sharp_threshold_var = tk.StringVar(value=settings["sharpen_threshold"])
        self.sharp_threshold_entry = ttk.Entry(
            self.process_frame,
            textvariable=self.sharp_threshold_var,
            width=10,
        )

        # 亮度选项
        self.bright_label = ttk.Label(self.process_frame, text="亮度:")
        self.bright_var = tk.StringVar(value=settings["brightness"])
        self.bright_entry = ttk.Entry(
            self.process_frame, textvariable=self.bright_var, width=10
        )

        # 输出格式选项
        self.format_frame = ttk.LabelFrame(self.root, text="输出设置", padding=10)

        self.format_label = ttk.Label(self.format_frame, text="输出格式:")
        self.format_var = tk.StringVar(value=settings["output_format"])
        self.format_combo = ttk.Combobox(
            self.format_frame,
            textvariable=self.format_var,
            values=["png", "bc3", "bc7"],
            state="readonly",
            width=10,
        )

        self.delete_png_var = tk.StringVar(value=settings["delete_temporary_png"])
        self.delete_png_check = ttk.Checkbutton(
            self.format_frame,
            text="删除临时PNG文件",
            variable=self.delete_png_var,
        )

        # 控制按钮
        self.control_frame = ttk.Frame(self.root)
        self.process_btn = ttk.Button(
            self.control_frame,
            text="开始处理",
            command=self.start_processing,
            style="Accent.TButton",
        )

        # 日志区域
        self.log_frame = ttk.LabelFrame(self.root, text="处理日志", padding=10)
        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, height=15, wrap=tk.WORD
        )
        self.log_text.config(state=tk.DISABLED)

        # 进度条
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")

    def setup_layout(self):
        # 处理选项布局
        self.process_frame.grid(
            row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )

        self.trim_check.grid(row=0, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.use_percent_size.grid(
            row=0, column=2, columnspan=3, padx=5, pady=5, sticky="w"
        )
        self.size_label.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")
        self.size_x_label.grid(row=2, column=0, padx=5, pady=2, sticky="w")
        self.size_x_entry.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.size_y_label.grid(row=2, column=2, padx=20, pady=2, sticky="w")
        self.size_y_entry.grid(row=2, column=3, padx=5, pady=2, sticky="w")

        self.sharp_label.grid(row=4, column=0, columnspan=4, padx=5, pady=5, sticky="w")
        self.sharp_percent_label.grid(row=5, column=0, padx=5, pady=2, sticky="w")
        self.sharp_percent_entry.grid(row=5, column=1, padx=5, pady=2, sticky="w")
        self.sharp_radius_label.grid(row=5, column=2, padx=20, pady=2, sticky="w")
        self.sharp_radius_entry.grid(row=5, column=3, padx=5, pady=2, sticky="w")
        self.sharp_threshold_label.grid(row=6, column=0, padx=5, pady=2, sticky="w")
        self.sharp_threshold_entry.grid(row=6, column=1, padx=5, pady=2, sticky="w")

        self.bright_label.grid(row=7, column=0, padx=5, pady=5, sticky="w")
        self.bright_entry.grid(row=7, column=1, padx=5, pady=5, sticky="w")

        self.process_frame.columnconfigure(3, weight=1)

        # 输出设置布局
        self.format_frame.grid(
            row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew"
        )
        self.format_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.format_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.delete_png_check.grid(row=0, column=2, padx=20, pady=5, sticky="w")

        # 控制按钮布局
        self.control_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=10)
        self.process_btn.pack(side=tk.LEFT, padx=5)

        # 进度条
        self.progress.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(5, weight=1)

        # 设置样式
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 10, "bold"))

    def log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    def clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def get_setting_dict(self):
        """从界面获取设置并转换为字典"""
        setting = {
            "use_trim": self.settings["use_trim"].get(),
            "size": [self.settings["size_x"].get(), self.settings["size_y"].get()],
            "sharpen_percent": self.settings["sharpen_percent"].get(),
            "sharpen_radius": self.settings["sharpen_radius"].get(),
            "sharpen_threshold": self.settings["sharpen_threshold"].get(),
            "brightness": self.settings["brightness"].get(),
            "output_format": self.settings["output_format"].get(),
            "delete_temporary_png": self.settings["delete_temporary_png"].get(),
        }
        return setting

    def start_processing(self):
        # 验证输入
        input_path = Path(self.input_entry.get())
        output_path = Path(self.output_entry.get())

        if not input_path.exists():
            messagebox.showerror("错误", "输入目录不存在！")
            return

        if not output_path.exists():
            try:
                output_path.mkdir(parents=True)
            except:
                messagebox.showerror("错误", "无法创建输出目录！")
                return

        # 开始处理
        self.process_btn.config(state=tk.DISABLED)
        self.progress.start()

        # 在新线程中处理，避免界面卡顿
        thread = threading.Thread(
            target=self.process_images, args=(input_path, output_path)
        )
        thread.daemon = True
        thread.start()

    def process_images(self, input_path, output_path):
        try:
            setting = self.get_setting_dict()

            # 获取输入文件
            input_subdir = self.get_input_files(input_path, setting)

            # 处理所有图片
            for dir_name, file_list in input_subdir.items():
                if dir_name == "imgs":
                    output_dir = output_path
                else:
                    output_dir.mkdir(exist_ok=True)

                for file_name, img, _ in file_list:
                    self.process_img(
                        file_name,
                        img,
                        dir_name if dir_name != "imgs" else None,
                        output_path,
                        setting,
                    )

            self.log_message("\n✅ 所有图片处理完成！")
            self.root.after(
                0, lambda: messagebox.showinfo("完成", "所有图片处理完成！")
            )

        except Exception as e:
            self.log_message(f"\n❌ 处理过程中发生错误: {str(e)}")
            self.log_message(traceback.format_exc())
            self.root.after(
                0, lambda: messagebox.showerror("错误", f"处理失败: {str(e)}")
            )
        finally:
            self.root.after(0, self.processing_done)

    def processing_done(self):
        self.progress.stop()
        self.process_btn.config(state=tk.NORMAL)

    def get_input_files(self, input_path, setting):
        input_subdir = {"imgs": []}

        for item in input_path.iterdir():
            self.log_message(f"📖 读取: {item.name}")

            if item.is_dir():
                input_subdir[item.name] = []

                for file in item.iterdir():
                    new_img = self.load_image(file, setting)
                    input_subdir[item.name].append((file.name, new_img, item.name))

            elif item.suffix.lower() in [".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
                new_img = self.load_image(item, setting)
                input_subdir["imgs"].append((item.name, new_img, None))

        return input_subdir

    def load_image(self, file, setting):
        try:
            with Image.open(file) as img:
                new_img = img.copy()

                if setting["use_trim"] and img.mode == "RGBA":
                    # 获取Alpha通道
                    alpha = img.getchannel("A")

                    # 裁剪图片
                    bbox = alpha.getbbox()
                    if bbox:
                        new_img = img.crop(bbox)
                        self.log_message(
                            f"📖 加载图片  {file.name} ({img.width}x{img.height}, 裁剪后{new_img.width}x{new_img.height})"
                        )
                    else:
                        self.log_message(
                            f"📖 加载图片  {file.name} ({img.width}x{img.height})"
                        )
                else:
                    self.log_message(
                        f"📖 加载图片  {file.name} ({img.width}x{img.height})"
                    )

            return new_img

        except Exception as e:
            self.log_message(f"❌ 加载图片失败 {file.name}: {str(e)}")
            raise

    def set_size_img(self, img, tw, th):
        width, height = img.size
        new_width = new_height = 1

        try:
            if tw and th:
                # 尝试转换为数字
                try:
                    tw_val = float(tw)
                    th_val = float(th)

                    # 如果是整数，直接使用
                    if tw.isdigit() and th.isdigit():
                        new_width = int(tw)
                        new_height = int(th)
                    else:
                        # 否则按比例缩放
                        new_width = round(width * tw_val)
                        new_height = round(height * th_val)

                    self.log_message(
                        f"🔎 缩放图片大小，从{width}x{height}到{new_width}x{new_height}"
                    )

                except ValueError:
                    self.log_message(f"⚠️  无效的缩放参数: {tw}, {th}")
                    return img
            else:
                return img

        except Exception as e:
            self.log_message(f"❌ 缩放失败: {str(e)}")
            return img

        return img.resize((new_width, new_height))

    def set_sharpen_img(self, img, percent, radius, threshold):
        """锐化"""
        try:
            percent_val = float(percent) if percent else 0
            radius_val = float(radius) if radius else 1.0
            threshold_val = int(threshold) if threshold else 0

            if percent_val > 0:
                sharpened = img.filter(
                    ImageFilter.UnsharpMask(
                        radius_val, percent_val / 100.0, threshold_val
                    )
                )
                self.log_message(
                    f"🔼 锐化图片，强度{percent_val}%，半径{radius_val}，阈值{threshold_val}"
                )
                return sharpened
            else:
                return img

        except Exception as e:
            self.log_message(f"❌ 锐化失败: {str(e)}")
            return img

    def set_brightness_img(self, img, brightness_factor):
        """亮度"""
        try:
            brightness_val = float(brightness_factor) if brightness_factor else 1.0

            if brightness_val != 1.0:
                enhancer = ImageEnhance.Brightness(img)
                compensated = enhancer.enhance(brightness_val)
                self.log_message(f"🔆 修改图片亮度为{brightness_val}倍")
                return compensated
            else:
                return img

        except Exception as e:
            self.log_message(f"❌ 调整亮度失败: {str(e)}")
            return img

    def process_img(self, name, img, in_dir, output_path, setting):
        try:
            output_img = None

            # 应用各项处理
            if setting["size"][0] or setting["size"][1]:
                img = self.set_size_img(img, setting["size"][0], setting["size"][1])
            if setting["sharpen_percent"]:
                img = self.set_sharpen_img(
                    img,
                    setting["sharpen_percent"],
                    setting["sharpen_radius"],
                    setting["sharpen_threshold"],
                )
            if setting["brightness"]:
                img = self.set_brightness_img(img, setting["brightness"])

            # 确定输出路径
            if in_dir:
                output_dir = output_path / in_dir
                output_dir.mkdir(exist_ok=True)
                output_img = output_dir / name
            else:
                output_img = output_path / name

            # 保存图片
            output_format = setting["output_format"]

            if output_format == "png":
                img.save(output_img)
                self.log_message(f"✅ 保存为PNG: {name}")
            elif output_format in ["bc3", "bc7"]:
                # 先保存为PNG临时文件
                temp_png = output_img.with_suffix(".png")
                img.save(temp_png)
                self.save_to_dds(temp_png, int(output_format[-1]), output_path, setting)
            else:
                img.save(output_img)
                self.log_message(f"🖼️ 保存图片: {name}")

        except Exception as e:
            self.log_message(f"❌ 处理图片失败 {name}: {str(e)}")
            raise

    def save_to_dds(self, output_file, bc, output_path, setting):
        """将PNG图片转换为DDS格式"""
        try:
            self.log_message(f"✅ 转换为DDS BC{bc}格式: {output_file.name}...")

            output_format = f"BC{bc}_UNORM"

            # 使用texconv工具进行格式转换
            result = run_texconv(output_format, output_file, output_path)

            if result.returncode == 0:
                self.log_message(f"✅ DDS转换成功: {output_file.stem}.dds")

                # 删除临时PNG文件
                if setting["delete_temporary_png"]:
                    Path(output_file).unlink()
                    self.log_message(f"🗑️  已删除临时PNG文件: {output_file.name}")
            else:
                self.log_message(f"❌ DDS转换失败: {result.stderr}")

        except Exception as e:
            self.log_message(f"❌ DDS转换失败: {str(e)}")


def main(root):
    app = ImageProcessorGUI(root)
