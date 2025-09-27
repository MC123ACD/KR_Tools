import os, re, sys, traceback, plistlib, imageio
import lupa.luajit20 as lupa
from lupa import LuaRuntime
from PIL import Image

# 添加上级目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from lib import lib

base_dir, input_path, output_path = lib.find_and_create_directory(__file__)
lua = lib.init_lua()


class SplitAtlases:
    def setup_lua_environment(self):
        # 注入自定义table函数
        lua.execute(
            """
        table.contains = function(t, value)
            for _, v in ipairs(t) do
                if v == value then return true end
            end
            return false
        end
        
        table.filter = function(t, func)
            local result = {}
            for k, v in ipairs(t) do
                if func(k, v) then
                    table.insert(result, v)
                end
            end
            return result
        end
        
        table.merge = function(t1, t2)
            for k, v in pairs(t2) do
                t1[k] = v
            end
        end
        
        math.ceil = function(x)
            return math.floor(x + 0.5)
        end
        """
        )

        # 定义核心转换函数
        lua.execute(
            """
        function to_xml(t, level)
            local function indent(l)
                local v = ""
                for i = 1, l do v = v .. "\\t" end
                return v
            end

            local o = ""
            if type(t) == "table" then
                if #t > 0 then
                    o = o .. indent(level) .. "<array>\\n"
                    for _, v in ipairs(t) do
                        o = o .. to_xml(v, level + 1)
                    end
                    o = o .. indent(level) .. "</array>\\n"
                else
                    o = o .. indent(level) .. "<dict>\\n"
                    for k, v in pairs(t) do
                        o = o .. indent(level + 1) .. "<key>" .. tostring(k) .. "</key>\\n"
                        o = o .. to_xml(v, level + 1)
                    end
                    o = o .. indent(level) .. "</dict>\\n"
                end
            elseif type(t) == "boolean" then
                o = o .. indent(level) .. (t and "<true/>" or "<false/>") .. "\\n"
            elseif type(t) == "number" then
                o = o .. indent(level) .. "<real>" .. tostring(t) .. "</real>\\n"
            elseif type(t) == "string" then
                o = o .. indent(level) .. "<string>" .. tostring(t) .. "</string>\\n"
            end
            return o
        end

        function to_plist(t, a_name, size)
            local o = ""
            o = o .. '<?xml version="1.0" encoding="UTF-8"?>\\n'
            o = o .. '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\\n'
            o = o .. '<plist version="1.0">\\n'
            o = o .. '\\t<dict>\\n'
            o = o .. '\\t\\t<key>frames</key>\\n'
            o = o .. to_xml(t, 2)
            o = o .. '\\t\\t<key>metadata</key>\\n'
            o = o .. '\\t\\t<dict>\\n'
            o = o .. '\\t\\t\\t<key>format</key>\\n'
            o = o .. '\\t\\t\\t<integer>3</integer>\\n'
            o = o .. '\\t\\t\\t<key>pixelFormat</key>\\n'
            o = o .. '\\t\\t\\t<string>RGBA8888</string>\\n'
            o = o .. '\\t\\t\\t<key>premultiplyAlpha</key>\\n'
            o = o .. '\\t\\t\\t<false/>\\n'
            o = o .. '\\t\\t\\t<key>realTextureFileName</key>\\n'
            o = o .. '\\t\\t\\t<string>' .. a_name .. '</string>\\n'
            o = o .. '\\t\\t\\t<key>size</key>\\n'
            o = o .. '\\t\\t\\t<string>' .. size .. '</string>\\n'
            o = o .. '\\t\\t\\t<key>textureFileName</key>\\n'
            o = o .. '\\t\\t\\t<string>' .. a_name .. '</string>\\n'
            o = o .. '\\t\\t</dict>\\n'
            o = o .. '\\t</dict>\\n'
            o = o .. '</plist>\\n'
            return o
        end

        function split_atlas(t)
            local t = require(t)

            if not t then
                return false
            end

            local atlases = {}
            local names = {}
            for k, v in pairs(t) do
                if not table.contains(names, v.a_name) then
                    table.insert(names, v.a_name)
                    local newAtlas = {size = "{" .. v.a_size[1] .. "," .. v.a_size[2] .. "}"}
                    atlases[v.a_name] = newAtlas
                end
                local atlas = atlases[v.a_name]
                local spriteWidth, spriteHeight = v.f_quad[3], v.f_quad[4]
                local spriteSourceWidth, spriteSourceHeight = v.size[1], v.size[2]
                local spriteOffsetX = math.ceil(v.trim[1] - (spriteSourceWidth - spriteWidth) / 2)
                local spriteOffsetY = math.floor((spriteSourceHeight - spriteHeight) / 2 - v.trim[2])
                local newTable = {
                    spriteOffset = "{" .. spriteOffsetX .. "," .. spriteOffsetY .. "}",
                    spriteSize = "{" .. spriteWidth .. "," .. spriteHeight .. "}",
                    spriteSourceSize = "{" .. spriteSourceWidth .. "," .. spriteSourceHeight .. "}",
                    textureRect = "{{" .. v.f_quad[1] .. "," .. v.f_quad[2] .. "},{" .. spriteWidth .. "," .. spriteHeight .. "}}",
                    textureRotated = v.textureRotated or false
                }
                atlas[k .. ".png"] = newTable
                if v.alias and #v.alias > 0 then
                    for _, alias in ipairs(v.alias) do
                        atlas[alias .. ".png"] = newTable
                    end
                end
            end
            return atlases
        end

        function value_to_string(t, level, key)
            local function indent(l)
                local v = ""
                for i = 1, l do v = v .. "\\t" end
                return v
            end

            local o = indent(level) .. (key and (key .. " = ") or "")
            if type(t) == "table" then
                if #t > 0 then
                    o = o .. "{\\n"
                    for _, v in ipairs(t) do
                        o = o .. value_to_string(v, level + 1)
                    end
                    o = o .. indent(level) .. "},\\n"
                else
                    o = o .. "{\\n"
                    for k, v in pairs(t) do
                        o = o .. value_to_string(v, level + 1, k)
                    end
                    o = o .. indent(level) .. "},\\n"
                end
            elseif type(t) == "boolean" then
                o = o .. (t and "true" or "false") .. ",\\n"
            elseif type(t) == "number" then
                o = o .. tostring(t) .. ",\\n"
            elseif type(t) == "string" then
                o = o .. '"' .. t .. '",\\n'
            end
            return o
        end
        """
        )
        return lua

    def clean_lua_content(self, content):
        """清理Lua文件内容，确保是有效的表格式"""
        # 移除 BOM
        content = re.sub(r"^\s*\ufeff\s*", "", content.strip())

        # 移除单行注释
        content = re.sub(r"--.*$", "", content, flags=re.MULTILINE)

        # 移除多行注释
        content = re.sub(r"--\[\[.*?\]\]", "", content, flags=re.DOTALL)

        # 移除开头的 'return' 关键字（如果有）
        content = re.sub(r"^\s*return\s*", "", content.strip())
        return content.strip()

    def gen_png_from_plist(self, plist_path, png_path, open_plist=None):
        """根据Plist文件和图集生成小图"""
        # 打开图集
        big_image = Image.open(png_path)

        # 读取并解析plist文件
        with open(plist_path, "rb") as file:
            if open_plist:
                root = open_plist
            else:
                root = plistlib.load(file)

            frames = root["frames"]

        # 辅助函数
        def to_int_list(x):
            return list(map(int, x.replace("{", "").replace("}", "").split(",")))

        def to_float_list(x):
            return list(map(float, x.replace("{", "").replace("}", "").split(",")))

        # 处理每个帧
        for frame_key in frames:
            frame_data = frames[frame_key]
            framename = frame_key.replace(".png", "")

            # 获取尺寸和位置信息
            sprite_size = to_int_list(frame_data["spriteSourceSize"])
            texture_rect = to_int_list(frame_data["textureRect"])
            offset = to_float_list(frame_data["spriteOffset"])

            # 计算裁剪框
            result_box = texture_rect.copy()
            if frame_data["textureRotated"]:
                result_box[0] = int(texture_rect[0])
                result_box[1] = int(texture_rect[1])
                # 交换宽高
                result_box[2] = int(texture_rect[0] + texture_rect[3])
                result_box[3] = int(texture_rect[1] + texture_rect[2])
            else:
                result_box[0] = int(texture_rect[0])
                result_box[1] = int(texture_rect[1])
                result_box[2] = int(texture_rect[0] + texture_rect[2])
                result_box[3] = int(texture_rect[1] + texture_rect[3])

            # 裁剪图集
            rect_on_big = big_image.crop(result_box)

            # 如果需要，旋转裁剪的图像
            if frame_data["textureRotated"]:
                rect_on_big = rect_on_big.transpose(Image.ROTATE_90)

            # 指定粘贴的位置（左上角坐标）
            position = (
                int((sprite_size[0] - texture_rect[2]) / 2 + offset[0]),
                int((sprite_size[1] - texture_rect[3]) / 2 - offset[1]),
            )

            # 创建新图像并粘贴裁剪的图像
            result_image = Image.new("RGBA", sprite_size, (0, 0, 0, 0))
            result_image.paste(rect_on_big, position)

            # 创建输出目录（如果不存在）
            output_dir = os.path.join(
                output_path,
                os.path.splitext(os.path.basename(plist_path))[0],
            )
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # 保存结果图像
            output_file = os.path.join(output_dir, framename + ".png")
            result_image.save(output_file)
            print(f"🖼️ 生成小图: {os.path.basename(output_file)}")

    def process_plist_conversion(self):
        """处理Plist文件生成并生成小图"""
        print(f"🔍 扫描目录: {input_path}")

        while len(os.listdir(input_path)) == 0:
            input("❌ 错误, 输入目录为空, 请放入图集与数据文件后按回车重试 >")

        try:
            for filename in os.listdir(input_path):
                if filename.endswith(".lua"):
                    filepath = os.path.join(input_path, filename)
                    print(f"📖 读取文件: {filename}")
                    filepath_lua = (
                        os.path.basename(input_path)
                        + "."
                        + filename.replace(".lua", "")
                    )

                    atlases = lua.globals().split_atlas(filepath_lua)

                    for a_name, atlas in atlases.items():
                        size = atlas["size"]
                        del atlas["size"]  # 移除size字段

                        # 提取基础文件名
                        match = re.search(r"\.(png|dds|pkm|pkm\.lz4)$", a_name)
                        if not match:
                            print(f"⚠️ 跳过无效文件名: {a_name}")
                            continue

                        base_name = a_name[: match.start()]
                        plist_filename = f"{base_name}.plist"
                        plist_path = os.path.join(output_path, plist_filename)

                        # 生成Plist内容
                        plist_data = lua.globals().to_plist(atlas, a_name, size)

                        # 写入Plist文件
                        with open(plist_path, "w", encoding="utf-8") as plist_file:
                            plist_file.write(plist_data)
                        print(f"✅ 生成Plist: {plist_filename}")

                        # 处理对应图集
                        atlas_image = os.path.join(input_path, a_name)
                        if os.path.exists(atlas_image):
                            # 生成小图
                            self.gen_png_from_plist(plist_path, atlas_image)
                        else:
                            print(f"⚠️ 图集不存在: {a_name}")

                elif filename.endswith(".plist"):
                    filepath = os.path.join(input_path, filename)
                    print(f"📖 读取文件: {filename}")

                    with open(filepath, "rb") as file:
                        open_plist = plistlib.load(file)
                        frames = open_plist["metadata"]["realTextureFileName"]

                    # for frame_key in frames:
                    atlas_image = os.path.join(input_path, frames)
                    if os.path.exists(atlas_image):
                        # 生成小图
                        self.gen_png_from_plist(filepath, atlas_image, open_plist)
                    else:
                        print(f"⚠️ 图集不存在: {frames}")

                else:
                    print(f"⚠️ 跳过无效文件: {a_name}")
                    continue
        except Exception as e:
            print(f"❌ 处理错误 {filename}: {str(e)}")
            traceback.print_exc()

    def process_animations(self, immutable_path, alterable_path):
        """处理动画文件"""
        print("\n🔄 处理动画文件...")
        immutable_anims = {}

        # 收集所有immutable动画
        if os.path.exists(immutable_path):
            for filename in os.listdir(immutable_path):
                if filename.endswith(".lua"):
                    filepath = os.path.join(immutable_path, filename)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                            if content.strip():
                                cleaned_content = self.clean_lua_content(content)
                                anims = lua.eval(f"return {cleaned_content}")
                                for k, v in anims.items():
                                    immutable_anims[k] = v
                        print(f"📥 加载: {filename} ({len(anims)}动画)")
                    except Exception as e:
                        print(f"❌ 加载错误 {filename}: {str(e)}")

        # 处理alterable文件
        if os.path.exists(alterable_path):
            alterable_files = [
                f for f in os.listdir(alterable_path) if f.endswith(".lua")
            ]

            if alterable_files:
                alterable_file = os.path.join(alterable_path, alterable_files[0])
                print(f"🛠️ 处理: {alterable_file}")

                try:
                    with open(alterable_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip():
                            cleaned_content = self.clean_lua_content(content)
                            alterable_anims = lua.eval(f"return {cleaned_content}")
                        else:
                            alterable_anims = {}
                            print("⚠️ 空文件，初始化为空表")

                    # 移除重复动画
                    original_count = len(alterable_anims)
                    for key in list(alterable_anims.keys()):
                        if key in immutable_anims:
                            del alterable_anims[key]

                    removed = original_count - len(alterable_anims)
                    print(f"🗑️ 移除 {removed} 个重复动画")

                    # 生成新内容
                    output_content = "return {\n"
                    for key, value in alterable_anims.items():
                        output_content += lua.globals().value_to_string(
                            value, 1, f'["{key}"]'
                        )
                    output_content += "}"

                    with open(alterable_file, "w", encoding="utf-8") as f:
                        f.write(output_content)
                    print(f"💾 保存更新: {alterable_file}")

                except Exception as e:
                    print(f"❌ 处理错误: {str(e)}")
                    traceback.print_exc()

    def process_dds_conversion(self, dds_path):
        """处理DDS到PKM转换"""
        print("\n🖼️ 处理纹理转换...")

        for filename in os.listdir(dds_path):
            if filename.endswith(".lua"):
                filepath = os.path.join(dds_path, filename)
                print(f"🔧 转换: {filename}")

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip():
                            cleaned_content = self.clean_lua_content(content)
                            atlas = lua.eval(f"{cleaned_content}")
                        else:
                            atlas = {}
                            print("⚠️ 空文件，初始化为空表")

                    # 更新a_name字段
                    updated = 0
                    for key, value in atlas.items():
                        if "a_name" in value and isinstance(value["a_name"], str):
                            if value["a_name"].endswith(".dds"):
                                value["a_name"] = re.sub(
                                    r"\.dds$", ".pkm.lz4", value["a_name"]
                                )
                                updated += 1

                    print(f"🔄 更新 {updated} 个纹理引用")

                    # 排序并生成新内容
                    keys = list(atlas.keys())
                    keys.sort()

                    output_content = "return {\n"
                    for key in keys:
                        output_content += lua.globals().value_to_string(
                            atlas[key], 1, f'["{key}"]'
                        )
                    output_content += "}"

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(output_content)
                    print(f"💾 保存: {filename}")

                except Exception as e:
                    print(f"❌ 转换错误: {str(e)}")
                    traceback.print_exc()

    def main(self):
        print("🚀 开始转换流程")
        print("=" * 50)

        # 处理Plist转换和小图生成
        self.process_plist_conversion()

        # 处理动画文件
        immutable_path = os.path.join(base_dir, "animations", "immutable")
        alterable_path = os.path.join(base_dir, "animations", "alterable")
        self.process_animations(immutable_path, alterable_path)

        # 处理纹理转换
        dds_path = os.path.join(base_dir, "dds2pkm_lz4")
        self.process_dds_conversion(dds_path)

        print("=" * 50)
        print("🎉 所有转换完成!")


if __name__ == "__main__":
    app = SplitAtlases()
    app.main()
    input("程序执行完毕，按回车键退出...")
