import traceback, config, subprocess
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import log

log = log.setup_logging(config.log_level, config.log_file)
# setting = config.setting["merge_images"]


def get_input_files_groups():
    groups = {}

    for item in config.input_path.iterdir():
        item_stem = item.stem
        print(f"📖 读取: {item.name}")

        if item.is_dir():
            if not groups.get(item_stem):
                groups[item_stem] = []

            for file in item.iterdir():
                with Image.open(file) as img:
                    new_img = img.copy()

                groups[item_stem].append([file.name, new_img])

    for group in groups.values():
        group.sort()

    return groups


def process_img(name, img, main_name, main_img):
    new_img = Image.alpha_composite(main_img, img)

    output_img = config.output_path / main_name

    new_img.save(output_img)

    print(f"🖼️ 保存图片: {main_name}")

    return new_img


def main():
    input_groups = get_input_files_groups()

    main_group_key = next(iter(input_groups))
    main_group = input_groups[main_group_key]

    for key, group in input_groups.items():
        if key == main_group_key:
            continue

        for idx, (name, img) in enumerate(group):
            main_group[idx][1] = process_img(
                name, img, main_group[idx][0], main_group[idx][1]
            )
