import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import lupa.luajit20 as lupa
from lupa import LuaRuntime
import json, os

lua = LuaRuntime(unpack_returned_tuples=True)


class WaveDataGenerator:
    def __init__(self, root):
        self.root = root
        self.root.title("波次数据生成器")
        self.root.geometry("1100x650")
        self.root.configure(bg="#f0f0f0")

        # 数据
        with open("./setting.json", "r", encoding="utf-8") as f:
            self.setting = json.load(f)

        # 波次数据
        self.setted = self.setting["setting"]
        self.default_wave_data = self.setting["default_wave_data"]
        self.default_criket = self.setting["default_criket"]
        if self.setted["time_to_s"]:
            self.default_wave_data["groups"]["wave_arrive_time"] = round(self.default_wave_data["groups"]["wave_arrive_time"] / 30, 2)
            self.default_wave_data["spawns"]["interval"] = round(self.default_wave_data["spawns"]["interval"] / 30, 2)
            self.default_wave_data["spawns"]["interval_next"] = round(self.default_wave_data["spawns"]["interval_next"] / 30, 2)

        self.wave_data = {"cash": self.default_wave_data["cash"], "groups": []}

        self.current_wave_index = 0
        self.last_listbox_selected = ""
        self.load_luafile = (
            "level01_waves_campaign"
            if not self.setted["Dove_spawn_criket"]
            else "criket"
        )

        # 创建UI
        self.create_widgets()

        # 添加初始波次
        self.add_wave()

        self.root.after(10, self.entry_focus, self.cash_entry)

    def create_widgets(self):
        # # 设置按钮
        # setting_frame = tk.Frame(self.root, bg="#f0f0f0")
        # setting_frame.pack(fill="x", padx=10, pady=5)
        # self.setting_btn = tk.Button(
        #     setting_frame,
        #     text="设置",
        #     command=self.setting_dialog,
        #     font=("Arial", 10),
        # )
        # self.setting_btn.pack(side="left", padx=5)

        set_frame = tk.Frame()
        set_frame.pack(fill="x", padx=10, pady=5)

        self.save_btn = tk.Button(
            set_frame,
            text="保存为Lua文件",
            command=self.save_to_lua,
            bg="#27ae60",
            fg="white",
            font=("Arial", 10),
        )
        self.save_btn.pack(side="left", padx=5)

        self.load_btn = tk.Button(
            set_frame,
            text="加载Lua文件",
            command=self.load_from_lua,
            bg="#9b59b6",
            fg="white",
            font=("Arial", 10),
        )
        self.load_btn.pack(side="left", padx=5)

        if not self.setted["Dove_spawn_criket"]:
            # 波次控制区域
            control_frame = tk.LabelFrame(
                self.root,
                text="波次管理",
                font=("Arial", 10, "bold"),
                bg="#f0f0f0",
                padx=10,
                pady=10,
            )
            control_frame.pack(fill="x", padx=10, pady=5)

            self.add_wave_btn = tk.Button(
                control_frame,
                text="添加新波次",
                command=self.add_wave,
                bg="#3498db",
                fg="white",
                font=("Arial", 10),
            )
            self.add_wave_btn.pack(side="left", padx=5)

            self.delete_wave_btn = tk.Button(
                control_frame,
                text="删除波次",
                command=self.delete_wave,
                bg="#e74c3c",
                fg="white",
                font=("Arial", 10),
            )
            self.delete_wave_btn.pack(side="left", padx=5)

        # 初始资源
        initial_resource_frame = tk.Frame(self.root, bg="#f0f0f0")
        initial_resource_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(initial_resource_frame, text="初始金币:", bg="#f0f0f0").pack(
            side="left", padx=5
        )
        self.cash_var = tk.StringVar(
            value=(
                self.default_wave_data["cash"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["cash"]
            )
        )
        self.cash_entry = ttk.Entry(
            initial_resource_frame, textvariable=self.cash_var, width=10
        )
        self.cash_entry.pack(side="left", padx=5)
        self.cash_entry.bind(
            "<Return>", lambda e, nw="spawn", i=0: self.on_enter(e, nw, i)
        )

        if not self.setted["Dove_spawn_criket"]:
            # 波次按钮区域
            self.wave_btn_frame = tk.Frame(self.root, bg="#f0f0f0")
            self.wave_btn_frame.pack(fill="x", padx=10, pady=5)

            # 波次参数
            wave_param_frame = tk.Frame(self.root, bg="#f0f0f0")
            wave_param_frame.pack(fill="x", padx=10, pady=5)

            tk.Label(
                wave_param_frame,
                text=(
                    "波次到来时间(秒):"
                    if self.setted["time_to_s"] or self.setted["Dove_spawn_criket"]
                    else "波次到来时间:"
                ),
                bg="#f0f0f0",
            ).pack(side="left", padx=(20, 5))
            self.wave_arrive_time_var = tk.StringVar(
                value=self.default_wave_data["groups"]["wave_arrive_time"]
            )
            self.wave_arrive_time_entry = ttk.Entry(
                wave_param_frame, textvariable=self.wave_arrive_time_var, width=10
            )
            self.wave_arrive_time_entry.pack(side="left", padx=5)
            self.wave_arrive_time_entry.bind(
                "<Return>", lambda e, nw="spawn", i=1: self.on_enter(e, nw, i)
            )

        # 波次编辑区域
        edit_frame = tk.Frame(self.root, bg="#f0f0f0")
        edit_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 左侧 - 出怪组管理
        group_frame = tk.LabelFrame(
            edit_frame,
            text="出怪组管理",
            font=("Arial", 10, "bold"),
            bg="#f0f0f0",
            padx=10,
            pady=10,
        )
        group_frame.pack(side="left", fill="y", padx=(0, 5))

        self.group_listbox = tk.Listbox(
            group_frame,
            width=25,
            height=15,
            font=("Arial", 10),
            bg="white",
            bd=2,
            relief="groove",
            exportselection=False,
        )
        self.group_listbox.pack(fill="both", expand=True, pady=(0, 10))
        self.group_listbox.bind("<<ListboxSelect>>", self.on_group_select)

        btn_frame = tk.Frame(group_frame, bg="#f0f0f0")
        btn_frame.pack(fill="x")

        self.add_group_btn = tk.Button(
            btn_frame,
            text="添加出怪组",
            command=self.add_group,
            bg="#3498db",
            fg="white",
            font=("Arial", 9),
        )
        self.add_group_btn.pack(side="left", fill="x", expand=True, padx=2)

        self.remove_group_btn = tk.Button(
            btn_frame,
            text="移除出怪组",
            command=self.remove_group,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 9),
        )
        self.remove_group_btn.pack(side="left", fill="x", expand=True, padx=2)

        # 右侧 - 出怪设置
        spawn_frame = tk.LabelFrame(
            edit_frame,
            text="出怪设置",
            font=("Arial", 10, "bold"),
            bg="#f0f0f0",
            padx=10,
            pady=10,
        )
        spawn_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        # 出怪组参数
        param_frame = tk.Frame(spawn_frame, bg="#f0f0f0")
        param_frame.pack(fill="x", pady=(0, 10))

        tk.Label(
            param_frame,
            text=(
                "当前出怪组延迟(秒):"
                if self.setted["time_to_s"] or self.setted["Dove_spawn_criket"]
                else "当前出怪组延迟:"
            ),
            bg="#f0f0f0",
        ).grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.delay_var = tk.StringVar()
        self.delay_entry = ttk.Entry(param_frame, textvariable=self.delay_var, width=8)
        self.delay_entry.grid(row=0, column=1, sticky="w", padx=5, pady=2)

        self.delay_entry.bind(
            "<Return>", lambda e, nw="spawn", i=2 if not self.setted["Dove_spawn_criket"] else 1: self.on_enter(e, nw, i)
        )

        tk.Label(param_frame, text="出怪路径:", bg="#f0f0f0").grid(
            row=0, column=2, sticky="e", padx=5, pady=2
        )
        self.path_index_var = tk.StringVar()
        self.path_index_entry = ttk.Entry(
            param_frame, textvariable=self.path_index_var, width=8
        )
        self.path_index_entry.grid(row=0, column=3, sticky="w", padx=5, pady=2)
        self.path_index_entry.bind(
            "<Return>", lambda e, nw="spawn", i=3 if not self.setted["Dove_spawn_criket"] else 2: self.on_enter(e, nw, i)
        )

        self.is_flying_check_var = tk.BooleanVar(value=False)
        
        # 创建第一个勾选框（默认选中）
        self.is_flying_check = ttk.Checkbutton(
            param_frame, 
            text="是否有飞行怪物", 
            variable=self.is_flying_check_var,
            command=self.on_checkbox_toggle
        )
        self.is_flying_check.grid(row=0, column=4, columnspan=2, sticky=tk.W, pady=5)

        # 怪物列表
        monster_list_frame = tk.Frame(spawn_frame, bg="#f0f0f0")
        monster_list_frame.pack(fill="both", expand=True)

        columns = (
            "creep",
            "creep_aux",
            "max_same",
            "max",
            "interval",
            "fixed_sub_path",
            "interval_next",
        )
        self.monster_tree = ttk.Treeview(
            monster_list_frame, columns=columns, show="headings", height=8
        )

        # 设置列
        self.monster_tree.heading("creep", text="怪物")
        self.monster_tree.heading("creep_aux", text="交替怪物")
        self.monster_tree.heading("max_same", text="交替数量")
        self.monster_tree.heading("max", text="总数量")
        self.monster_tree.heading(
            "interval",
            text=(
                "间隔(秒)"
                if self.setted["time_to_s"] or self.setted["Dove_spawn_criket"]
                else "间隔"
            ),
        )
        self.monster_tree.heading("fixed_sub_path", text="出怪子路径")
        self.monster_tree.heading(
            "interval_next",
            text=(
                "下一出怪延迟(秒)"
                if self.setted["time_to_s"] or self.setted["Dove_spawn_criket"]
                else "下一出怪延迟"
            ),
        )

        # 设置列宽
        self.monster_tree.column("creep", width=100, anchor="center")
        self.monster_tree.column("creep_aux", width=100, anchor="center")
        self.monster_tree.column("max_same", width=65, anchor="center")
        self.monster_tree.column("max", width=75, anchor="center")
        self.monster_tree.column("interval", width=60, anchor="center")
        self.monster_tree.column("fixed_sub_path", width=80, anchor="center")
        self.monster_tree.column("interval_next", width=80, anchor="center")

        self.monster_tree.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(
            monster_list_frame, orient="vertical", command=self.monster_tree.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.monster_tree.configure(yscrollcommand=scrollbar.set)

        # 怪物操作按钮
        monster_btn_frame = tk.Frame(spawn_frame, bg="#f0f0f0")
        monster_btn_frame.pack(fill="x", pady=(10, 0))

        self.add_monster_btn = tk.Button(
            monster_btn_frame,
            text="添加怪物",
            command=self.add_monster,
            bg="#3498db",
            fg="white",
            font=("Arial", 9),
        )
        self.add_monster_btn.pack(side="left", padx=2, pady=5)

        self.edit_monster_btn = tk.Button(
            monster_btn_frame,
            text="编辑怪物",
            command=self.edit_monster,
            bg="#f39c12",
            fg="white",
            font=("Arial", 9),
        )
        self.edit_monster_btn.pack(side="left", padx=2, pady=5)

        self.remove_monster_btn = tk.Button(
            monster_btn_frame,
            text="移除怪物",
            command=self.remove_monster,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 9),
        )
        self.remove_monster_btn.pack(side="left", padx=2, pady=5)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            bd=1,
            relief="sunken",
            anchor="w",
            bg="#f0f0f0",
            fg="#333333",
            font=("Arial", 9),
        )
        status_bar.pack(side="bottom", fill="x", padx=10, pady=5)

        # 初始化按钮
        if not self.setted["Dove_spawn_criket"]:
            self.update_wave_buttons()

    def on_checkbox_toggle(self):
        """当勾选框状态变化时调用"""
        selected = self.group_listbox.curselection()
        if not selected:
            return
        
        group_index = selected[0]
        group = self.wave_data["groups"][self.current_wave_index]["waves"][group_index]
        
        if self.is_flying_check_var.get():
            group["some_flying"] = True
        else:
            group["some_flying"] = False

    def setting_dialog(self):
        self.dialog = tk.Toplevel(self.root)
        self.dialog.title("设置")
        self.dialog.geometry("600x400")
        self.dialog.transient(self.root)
        self.dialog.grab_set()

        frame = tk.Frame(self.dialog, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        control_frame = tk.LabelFrame(
            frame,
            text="启用怪物",
            font=("Arial", 10, "bold"),
            bg="#f0f0f0",
            padx=10,
            pady=10,
        )
        control_frame.pack(side="left", padx=10, pady=5)

        for i in range(4):
            self.setting_btn = tk.Button(
                control_frame,
                text="设置",
                command=self.setting_dialog,
                font=("Arial", 10),
            )
            self.setting_btn.pack(side="left", padx=5)

    def update_wave_buttons(self):
        # 清除现有的波次按钮
        for widget in self.wave_btn_frame.winfo_children():
            widget.destroy()

        # 添加新的波次按钮
        for i, group in enumerate(self.wave_data["groups"]):
            btn = tk.Button(
                self.wave_btn_frame,
                text=f"第{i+1}波",
                command=lambda idx=i: self.select_wave(idx),
                bg="#9b59b6" if i == self.current_wave_index else "#ecf0f1",
                fg="white" if i == self.current_wave_index else "black",
                font=("Arial", 10, "bold"),
            )
            btn.pack(side="left", padx=5, pady=5)

    def add_wave(self):
        if not self.setted["Dove_spawn_criket"]:
            self.last_listbox_selected = ""

            self.save_initial_resource()
            self.save_wave(set_origin=False)

        new_wave = {
            "wave_arrive_time": self.default_wave_data["groups"]["wave_arrive_time"],
            "waves": [],
        }
        self.wave_data["groups"].append(new_wave)
        self.current_wave_index = len(self.wave_data["groups"]) - 1

        if not self.setted["Dove_spawn_criket"]:
            self.wave_arrive_time_var.set(
                self.wave_data["groups"][self.current_wave_index]["wave_arrive_time"]
            )

            self.update_wave_buttons()
            self.clear_group_list()

            self.root.after(3, self.entry_focus, self.wave_arrive_time_entry)

        self.add_group()

        self.status_var.set(f"已添加第{self.current_wave_index+1}波")

    def delete_wave(self):
        if len(self.wave_data["groups"]):
            self.last_listbox_selected = ""
            self.save_initial_resource()

            del self.wave_data["groups"][self.current_wave_index]
            self.current_wave_index = max(0, self.current_wave_index - 1)

            self.update_wave_buttons()
            self.load_current_wave()

            self.group_listbox.selection_clear(0, tk.END)
            self.group_listbox.selection_set(0)
            self.on_group_select()

            self.entry_focus(self.wave_arrive_time_entry)

            self.status_var.set(f"已删除第{self.current_wave_index+1}波")

    def select_wave(self, index):
        self.last_listbox_selected = ""
        self.save_wave(set_origin=False)
        self.save_initial_resource()
        self.current_wave_index = index
        self.wave_arrive_time_var.set(
            self.wave_data["groups"][self.current_wave_index]["wave_arrive_time"]
        )
        self.update_wave_buttons()
        self.load_current_wave()
        self.group_listbox.selection_clear(0, tk.END)
        self.group_listbox.selection_set(0)
        self.on_group_select()

        self.entry_focus(self.delay_entry)

        self.status_var.set(f"已选择第{self.current_wave_index+1}波")

    def load_current_wave(self):
        if self.current_wave_index < 0:
            return

        wave = self.wave_data["groups"][self.current_wave_index]

        # 加载出怪组
        self.group_listbox.delete(0, tk.END)
        for i, _ in enumerate(wave["waves"]):
            self.group_listbox.insert(tk.END, f"出怪组 {i+1}")

        # 清空怪物列表
        self.clear_monster_tree()

    def clear_group_list(self):
        self.group_listbox.delete(0, tk.END)
        self.clear_monster_tree()

    def clear_monster_tree(self):
        for item in self.monster_tree.get_children():
            self.monster_tree.delete(item)

    def add_group(self):
        if self.current_wave_index < 0:
            messagebox.showwarning("警告", "请先选择或添加一个波次")
            return

        new_group = {
            "some_flying": self.default_wave_data["waves"]["some_flying"],
            "delay": (
                self.default_wave_data["waves"]["delay"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["waves"]["delay"]
            ),
            "path_index": (
                self.default_wave_data["waves"]["path_index"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["waves"]["path_index"]
            ),
            "spawns": [],
        }
        self.wave_data["groups"][self.current_wave_index]["waves"].append(new_group)
        group_index = (
            len(self.wave_data["groups"][self.current_wave_index]["waves"]) - 1
        )
        self.group_listbox.insert(tk.END, f"出怪组 {group_index+1}")
        self.group_listbox.selection_clear(0, tk.END)
        self.group_listbox.selection_set(group_index)
        self.on_group_select()
        self.status_var.set(f"已添加出怪组 {group_index+1}")

    def remove_group(self):
        self.last_listbox_selected = ""
        if self.current_wave_index < 0:
            return

        selected = self.group_listbox.curselection()
        if not selected:
            messagebox.showwarning("警告", "请先选择一个出怪组")
            return

        index = selected[0]
        self.wave_data["groups"][self.current_wave_index]["waves"].pop(index)
        self.group_listbox.delete(index)
        self.clear_monster_tree()
        self.renumber_all_groups()
        self.status_var.set(f"已移除出怪组 {index+1}")
        self.delay_var.set(self.default_wave_data["waves"]["delay"])
        self.path_index_var.set(self.default_wave_data["waves"]["path_index"])
        self.group_listbox.selection_clear(0, tk.END)
        self.group_listbox.selection_set(selected[0] - 1)
        self.on_group_select()

    def renumber_all_groups(self):
        self.group_listbox.delete(0, tk.END)
        for i in range(len(self.wave_data["groups"][self.current_wave_index]["waves"])):
            self.group_listbox.insert(tk.END, f"出怪组 {i+1}")

    def on_group_select(self, event=None):
        selected = self.group_listbox.curselection()
        if not selected:
            return

        self.save_wave()

        self.last_listbox_selected = selected[0]

        group_index = selected[0]
        wave_group = self.wave_data["groups"][self.current_wave_index]["waves"][
            group_index
        ]

        self.root.after(1, self.entry_focus, self.delay_entry)

        # 加载怪物
        self.clear_monster_tree()
        for spawn in wave_group["spawns"]:
            m = []
            for _, v in spawn.items():
                m.append(v)
            self.monster_tree.insert("", "end", values=(m))

    def add_monster(self):
        if not self.group_listbox.curselection():
            messagebox.showwarning("警告", "请先选择一个出怪组")
            return

        # 创建添加怪物对话框
        self.add_monster_dialog()

    def edit_monster(self):
        selected_group = self.group_listbox.curselection()
        if not selected_group:
            messagebox.showwarning("警告", "请先选择一个出怪组")
            return

        selected_monster = self.monster_tree.selection()
        if not selected_monster:
            messagebox.showwarning("警告", "请先选择一个怪物")
            return

        group_index = selected_group[0]
        monster_index = self.monster_tree.index(selected_monster[0])
        wave_group = self.wave_data["groups"][self.current_wave_index]["waves"][
            group_index
        ]
        spawn = wave_group["spawns"][monster_index]

        # 创建编辑怪物对话框
        self.add_monster_dialog(monster_index, spawn, edit=True)

    def remove_monster(self):
        selected_group = self.group_listbox.curselection()
        if not selected_group:
            return

        selected_monster = self.monster_tree.selection()
        if not selected_monster:
            return

        group_index = selected_group[0]
        monster_index = self.monster_tree.index(selected_monster[0])

        wave_group = self.wave_data["groups"][self.current_wave_index]["waves"][
            group_index
        ]
        wave_group["spawns"].pop(monster_index)

        self.monster_tree.delete(selected_monster[0])
        self.status_var.set(f"已移除怪物")

    def add_monster_dialog(self, monster_index=None, spawn=None, edit=None):
        self.dialog = tk.Toplevel(self.root)
        self.dialog.title(
            "添加怪物" if monster_index is None and edit != True else "编辑怪物"
        )
        self.dialog.geometry("400x400")
        self.dialog.transient(self.root)
        self.dialog.grab_set()

        monsters_key = [k for k, _ in self.load_monsters().items()]
        monsters_key[0] = ""
        # 创建表单
        form_frame = tk.Frame(self.dialog, padx=10, pady=10)
        form_frame.pack(fill="both", expand=True)

        # 怪物选择
        tk.Label(form_frame, text="怪物:").grid(
            row=0, column=0, sticky="e", padx=5, pady=5
        )
        creep_var = tk.StringVar()
        self.creep_combo = ttk.Combobox(
            form_frame, textvariable=creep_var, state="readonly", height=20
        )
        self.creep_combo["values"] = monsters_key
        self.creep_combo.grid(row=0, column=1, sticky="we", padx=5, pady=5)

        tk.Label(form_frame, text="交替怪物:").grid(
            row=1, column=0, sticky="e", padx=5, pady=5
        )
        creep_aux_var = tk.StringVar()
        self.creep_aux_combo = ttk.Combobox(
            form_frame, textvariable=creep_aux_var, state="readonly", height=20
        )
        self.creep_aux_combo["values"] = monsters_key
        self.creep_aux_combo.grid(row=1, column=1, sticky="we", padx=5, pady=5)

        # 参数设置
        tk.Label(form_frame, text="交替出怪数量:").grid(
            row=2, column=0, sticky="e", padx=5, pady=5
        )
        self.max_same_var = tk.StringVar(
            value=(
                self.default_wave_data["spawns"]["max_same"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["spawns"]["max_same"]
            )
        )
        self.max_same_entry = ttk.Entry(form_frame, textvariable=self.max_same_var)
        self.max_same_entry.grid(row=2, column=1, sticky="we", padx=5, pady=5)
        self.max_same_entry.bind(
            "<Return>", lambda e, nw="monster", i=0: self.on_enter(e, nw, i)
        )

        tk.Label(form_frame, text="总出怪数量:").grid(
            row=3, column=0, sticky="e", padx=5, pady=5
        )
        self.max_var = tk.StringVar(
            value=(
                self.default_wave_data["spawns"]["max"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["spawns"]["max"]
            )
        )
        self.max_entry = ttk.Entry(form_frame, textvariable=self.max_var)
        self.max_entry.grid(row=3, column=1, sticky="we", padx=5, pady=5)
        self.max_entry.bind(
            "<Return>", lambda e, nw="monster", i=1: self.on_enter(e, nw, i)
        )

        tk.Label(
            form_frame,
            text=(
                "间隔(秒):"
                if self.setted["time_to_s"] or self.setted["Dove_spawn_criket"]
                else "间隔:"
            ),
        ).grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.interval_var = tk.StringVar(
            value=(
                self.default_wave_data["spawns"]["interval"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["spawns"]["interval"]
            )
        )
        self.interval_entry = ttk.Entry(form_frame, textvariable=self.interval_var)
        self.interval_entry.grid(row=4, column=1, sticky="we", padx=5, pady=5)
        self.interval_entry.bind(
            "<Return>", lambda e, nw="monster", i=2: self.on_enter(e, nw, i)
        )

        tk.Label(form_frame, text="出怪子路径:").grid(
            row=5, column=0, sticky="e", padx=5, pady=5
        )
        self.fixed_sub_path_var = tk.StringVar(
            value=(
                self.default_wave_data["spawns"]["fixed_sub_path"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["spawns"]["fixed_sub_path"]
            )
        )
        self.fixed_sub_path_entry = ttk.Entry(
            form_frame, textvariable=self.fixed_sub_path_var
        )
        self.fixed_sub_path_entry.grid(row=5, column=1, sticky="we", padx=5, pady=5)
        self.fixed_sub_path_entry.bind(
            "<Return>", lambda e, nw="monster", i=3: self.on_enter(e, nw, i)
        )

        tk.Label(
            form_frame,
            text=(
                "下一出怪延迟(秒):"
                if self.setted["time_to_s"] or self.setted["Dove_spawn_criket"]
                else "下一出怪延迟:"
            ),
        ).grid(row=6, column=0, sticky="e", padx=5, pady=5)
        self.interval_next_var = tk.StringVar(
            value=(
                self.default_wave_data["spawns"]["interval_next"]
                if not self.setted["Dove_spawn_criket"]
                else self.default_criket["spawns"]["interval_next"]
            )
        )
        self.interval_next_entry = ttk.Entry(
            form_frame, textvariable=self.interval_next_var
        )
        self.interval_next_entry.grid(row=6, column=1, sticky="we", padx=5, pady=5)
        self.interval_next_entry.bind(
            "<Return>", lambda e, nw="monster", i=4: self.on_enter(e, nw, i)
        )

        # 填充现有数据（编辑模式）
        if spawn and edit:
            for k, _ in self.load_monsters(is_all=True).items():
                if k == spawn["creep"]:
                    creep_var.set(k)
                if k == spawn["creep_aux"]:
                    creep_aux_var.set(k)

            self.max_same_var.set(spawn["max_same"])
            self.max_var.set(spawn["max"])
            self.interval_var.set(spawn["interval"])
            self.fixed_sub_path_var.set(spawn["fixed_sub_path"])
            self.interval_next_var.set(spawn["interval_next"])

        # 确认按钮
        btn_frame = tk.Frame(self.dialog)
        btn_frame.pack(fill="x", padx=10, pady=10)

        tk.Button(
            btn_frame,
            text="保存",
            command=self.save_monster if not edit else self.edit_update_monster,
            bg="#27ae60",
            fg="white",
        ).pack(side="right", padx=5)
        tk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(
            side="right", padx=5
        )

        self.entry_focus(self.max_same_entry)

    def save_monster(self):
        selected_group = self.group_listbox.curselection()
        if not selected_group:
            return

        group_index = selected_group[0]

        wave_group = self.wave_data["groups"][self.current_wave_index]["waves"][
            group_index
        ]
        m = []

        new_spawn = self.load_monster_data()

        # 添加新怪物
        wave_group["spawns"].append(new_spawn)

        for i, v in new_spawn.items():
            if i == "creep" and not v:
                messagebox.showwarning("警告", "请选择怪物")
                return
            m.append(v)

        self.monster_tree.insert("", "end", values=(m))
        self.status_var.set("已添加怪物")

        self.dialog.destroy()

    def edit_update_monster(self):
        selected_group = self.group_listbox.curselection()
        if not selected_group:
            return

        selected_monster = self.monster_tree.selection()
        if not selected_monster:
            monster_index = None
        else:
            monster_index = self.monster_tree.index(selected_monster[0])

        group_index = selected_group[0]

        wave_group = self.wave_data["groups"][self.current_wave_index]["waves"][
            group_index
        ]
        m = []

        new_spawn = self.load_monster_data()

        # 更新现有怪物
        wave_group["spawns"][monster_index] = new_spawn

        for k, v in new_spawn.items():
            if k == "creep" and not v:
                messagebox.showwarning("警告", "请选择怪物")
                return
            m.append(v)

        self.monster_tree.item(
            self.monster_tree.get_children()[monster_index], values=(m)
        )
        self.status_var.set("已更新怪物")

        self.dialog.destroy()

    def load_monster_data(self):
        dictionary = {
            "creep": self.creep_combo.get(),
            "creep_aux": self.creep_aux_combo.get(),
            "max_same": int(self.max_same_var.get() if self.max_same_var.get() else 0),
            "max": int(self.max_var.get()),
            "interval": float(self.interval_var.get()),
            "fixed_sub_path": int(self.fixed_sub_path_var.get()),
            "interval_next": float(self.interval_next_var.get()),
        }

        return dictionary

    def save_to_lua(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".lua",
            filetypes=[("Lua 文件", "*.lua")],
            initialfile=self.load_luafile,
        )

        self.save_initial_resource()
        if self.group_listbox.curselection():
            self.save_wave()

        monsters = self.load_monsters(is_all=True)

        if not file_path:
            return

        try:
            if not self.setted["Dove_spawn_criket"]:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("return {\n")
                    f.write(f"    cash = {self.wave_data["cash"]},\n")
                    f.write("    live = 20,\n")
                    f.write("    groups = {\n")

                    for group_idx, group in enumerate(self.wave_data["groups"]):
                        if self.setted["time_to_s"]:
                            group["wave_arrive_time"] *= 30

                        f.write(f"        {{    -- 第{group_idx+1}波\n")
                        f.write(
                            f"            interval = {group["wave_arrive_time"]},\n"
                        )
                        f.write("            waves = {\n")

                        for wave_idx, wave in enumerate(group["waves"]):
                            if self.setted["time_to_s"]:
                                wave["delay"] *= 30

                            f.write(f"                {{    -- 第{wave_idx+1}组出怪\n")
                            f.write(f"                    some_flying = {"true" if wave["some_flying"] else "false"},\n")
                            f.write(f"                    delay = {wave["delay"]},\n")
                            f.write(
                                f"                    path_index = {wave["path_index"]},\n"
                            )
                            f.write("                    spawns = {\n")

                            for spawn_idx, spawn in enumerate(wave["spawns"]):
                                if self.setted["time_to_s"]:
                                    spawn["interval"] *= 30
                                    spawn["interval_next"] *= 30

                                f.write(
                                    f"                        {{    -- 出怪 {spawn_idx+1}\n"
                                )
                                f.write(
                                    f'                            creep = "{monsters[spawn["creep"]]}",\n'
                                )
                                if spawn["creep_aux"]:
                                    f.write(
                                        f'                            creep_aux = "{monsters[spawn["creep_aux"]]}",\n'
                                    )
                                f.write(
                                    f"                            max_same = {spawn["max_same"]},\n"
                                )
                                f.write(
                                    f"                            max = {spawn["max"]},\n"
                                )
                                f.write(
                                    f"                            interval = {spawn["interval"]},\n"
                                )
                                f.write(
                                    f"                            fixed_sub_path = {spawn["fixed_sub_path"]},\n"
                                )
                                f.write(
                                    f"                            interval_next = {spawn["interval_next"]}\n"
                                )
                                f.write(
                                    "                        },\n"
                                    if spawn_idx < len(wave["spawns"]) - 1
                                    else "                        }\n"
                                )

                            f.write("                    }\n")
                            f.write(
                                "                },\n"
                                if wave_idx < len(group["waves"]) - 1
                                else "                }\n"
                            )

                        f.write("            }\n")
                        f.write(
                            "        },\n"
                            if group_idx < len(self.wave_data["groups"]) - 1
                            else "        }\n"
                        )

                    f.write("    }\n")
                    f.write("}\n")

            else:
                groups = self.wave_data["groups"][0]["waves"]
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("return {\n")
                    f.write("    on = true,\n")
                    f.write(f"    cash = {self.wave_data["cash"]},\n")
                    f.write("    groups = {\n")

                    for group_idx, group in enumerate(groups):
                        group["delay"] *= 30

                        f.write(f"        {{    -- 第{group_idx+1}组出怪\n")
                        f.write(f"            delay = {group["delay"]},\n")
                        f.write(f"            path_index = {group["path_index"]},\n")
                        f.write("            spawns = {\n")

                        for spawn_idx, spawn in enumerate(group["spawns"]):
                            f.write(f"                {{    -- 出怪 {spawn_idx+1}\n")
                            f.write(
                                f'                    creep = "{monsters[spawn["creep"]]}",\n'
                            )
                            if spawn["creep_aux"]:
                                f.write(
                                    f'                    creep_aux = "{monsters[spawn["creep_aux"]]}",\n'
                                )
                            f.write(
                                f"                    max_same = {spawn["max_same"]},\n"
                            )
                            f.write(f"                    max = {spawn["max"]},\n")
                            f.write(
                                f"                    interval = {spawn["interval"]},\n"
                            )
                            f.write(
                                f"                    fixed_sub_path = {spawn["fixed_sub_path"]},\n"
                            )
                            f.write(
                                f"                    interval_next = {spawn["interval_next"]}\n"
                            )
                            f.write(
                                "                },\n"
                                if spawn_idx < len(group["spawns"]) - 1
                                else "                }\n"
                            )
                        f.write("            }\n")
                        f.write(
                            "        },\n"
                            if group_idx != len(groups) - 1
                            else "        }\n"
                        )
                    f.write("    },\n")
                    f.write("    required_textures = {    -- 启用的贴图列表\n")

                    for i, v in enumerate(self.default_criket["go_enemies_acaroth"]):
                        f.write(
                            f'        "{v}",\n'
                            if i != len(self.default_criket["go_enemies_acaroth"]) - 1
                            else f'        "{v}"\n'
                        )

                    f.write("    }\n")
                    f.write("}")

            self.status_var.set(f"文件已保存: {os.path.basename(file_path)}")
            messagebox.showinfo("成功", "Lua文件保存成功！")

        except Exception as e:
            messagebox.showerror("错误", f"保存文件时出错:\n{str(e)}")

    def load_from_lua(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Lua 文件", "*.lua"), ("所有文件", "*.*")]
        )

        if not file_path:
            return

        # 文件加载路径
        luafile = os.path.basename(file_path).replace(".lua", "")
        luafile_path = (
            file_path.replace(os.path.basename(file_path), "?")
            .replace("/", "\\")
            .replace("D", "d")
        )

        # 读取并返回lua文件的内容的函数
        lua.execute(
            """
        function load_lua(luafile, luafile_path)
            package.path = package.path .. ";" .. luafile_path .. ".lua"
            local l = require(luafile)

            local t = {
                cash = l.cash,
                groups = l.groups
            }

            return t
            end
            """
        )

        try:
            if not self.setted["Dove_spawn_criket"]:
                data = lua.globals().load_lua(luafile, luafile_path)
                monsters = self.load_monsters(is_all=True)
                wave_data = self.wave_data
                wave_data["groups"] = []

                wave_data["cash"] = data.cash

                for wave in range(1, len(data.groups) + 1):
                    new_wave_data = {
                        "wave_arrive_time": data.groups[wave].interval,
                        "waves": [],
                    }

                    if self.setted["time_to_s"]:
                        new_wave_data["wave_arrive_time"] = round(
                            new_wave_data["wave_arrive_time"] / 30, 2
                        )

                    d_waves = data.groups[wave].waves
                    for group in range(1, len(d_waves) + 1):
                        new_group_data = {
                            "some_flying": True if "some_flying" in d_waves[group] else False,
                            "delay": d_waves[group].delay,
                            "path_index": d_waves[group].path_index,
                            "spawns": [],
                        }

                        if self.setted["time_to_s"]:
                            new_group_data["delay"] = round(
                                new_group_data["delay"] / 30, 2
                            )

                        d_spawns = d_waves[group].spawns
                        for spawn in range(1, len(d_spawns) + 1):
                            new_spawn_data = {
                                "creep": monsters["reversal"][d_spawns[spawn].creep],
                                "creep_aux": (
                                    monsters["reversal"][d_spawns[spawn].creep_aux]
                                    if d_spawns[spawn].creep_aux
                                    else ""
                                ),
                                "max_same": (
                                    d_spawns[spawn].max_same
                                    if d_spawns[spawn].max_same
                                    else 0
                                ),
                                "max": d_spawns[spawn].max,
                                "interval": d_spawns[spawn].interval,
                                "fixed_sub_path": d_spawns[spawn].fixed_sub_path,
                                "interval_next": d_spawns[spawn].interval_next,
                            }

                            if self.setted["time_to_s"]:
                                new_spawn_data["interval"] = round(
                                    new_spawn_data["interval"] / 30, 2
                                )
                                new_spawn_data["interval_next"] = round(
                                    new_spawn_data["interval_next"] / 30, 2
                                )

                            new_group_data["spawns"].append(new_spawn_data)

                        new_wave_data["waves"].append(new_group_data)

                    wave_data["groups"].append(new_wave_data)
            else:
                data = lua.globals().load_lua(luafile, luafile_path)
                monsters = self.load_monsters(is_all=True)
                wave_data = self.wave_data
                wave_data["groups"] = [{"wave_arrive_time": 0, "waves": []}]

                wave_data["cash"] = data.cash

                d_groups = data.groups
                for group in range(1, len(d_groups) + 1):
                    new_group_data = {
                        "delay": d_groups[group].delay,
                        "path_index": d_groups[group].path_index,
                        "spawns": [],
                    }

                    d_spawns = d_groups[group].spawns
                    for spawn in range(1, len(d_spawns) + 1):
                        new_spawn_data = {
                            "creep": monsters["reversal"][d_spawns[spawn].creep],
                            "creep_aux": (
                                monsters["reversal"][d_spawns[spawn].creep_aux]
                                if d_spawns[spawn].creep_aux
                                else ""
                            ),
                            "max_same": (
                                d_spawns[spawn].max_same
                                if d_spawns[spawn].max_same
                                else 0
                            ),
                            "max": d_spawns[spawn].max,
                            "interval": d_spawns[spawn].interval,
                            "fixed_sub_path": d_spawns[spawn].fixed_sub_path,
                            "interval_next": d_spawns[spawn].interval_next,
                        }

                        new_group_data["spawns"].append(new_spawn_data)

                    wave_data["groups"][0]["waves"].append(new_group_data)

            self.current_wave_index = 0
            self.cash_var.set(data.cash)

        except Exception as e:
            messagebox.showerror("错误", f"加载文件时出错:\n{str(e)}")

        if not self.setted["Dove_spawn_criket"]:
            self.update_wave_buttons()
            self.wave_arrive_time_var.set(wave_data["groups"][0]["wave_arrive_time"])

        self.load_current_wave()
        self.group_listbox.selection_clear(0, tk.END)
        self.group_listbox.selection_set(0)
        self.on_group_select()

        if not self.setted["Dove_spawn_criket"]:
            self.load_luafile = luafile

        self.status_var.set(f"已加载 {luafile} 文件")

    def save_initial_resource(self):
        wave_data = self.wave_data
        group = wave_data["groups"]
        if group:
            wave = group[self.current_wave_index]

            wave_data["cash"] = int(self.cash_var.get())
            if not self.setted["Dove_spawn_criket"]:
                wave["wave_arrive_time"] = float(self.wave_arrive_time_var.get())

    def save_wave(self, set_origin=True):
        group = self.wave_data["groups"]
        if group:
            wave = group[self.current_wave_index]
            waves = wave["waves"]

            if waves:
                if set_origin and self.last_listbox_selected != "":
                    groups = waves[self.last_listbox_selected]
                    groups["delay"] = float(self.delay_var.get())
                    groups["path_index"] = int(self.path_index_var.get())

                if self.group_listbox.curselection():
                    wave_group = waves[self.group_listbox.curselection()[0]]

                    if set_origin:
                        self.is_flying_check_var.set(wave_group["some_flying"])
                        self.delay_var.set(wave_group["delay"])
                        self.path_index_var.set(wave_group["path_index"])
                    else:
                        wave_group["delay"] = float(self.delay_var.get())
                        wave_group["path_index"] = int(self.path_index_var.get())
                        self.delay_var.set("")
                        self.path_index_var.set("")

    def load_monsters(self, is_all=False):
        m = {"reversal": {}}

        for key, value in self.setting["monsters"].items():
            if is_all:
                for k, v in value.items():
                    m[k] = v
                    m["reversal"][v] = k
            elif self.setted["enabled_" + key]:
                for k, v in value.items():
                    m[k] = v
                    m["reversal"][v] = k

        return m

    def on_enter(self, event, next_widget, index):
        """回车时聚焦下一个控件"""
        widget = {}
        if next_widget == "spawn":
            if not self.setted["Dove_spawn_criket"]:
                widget["spawn"] = [
                    self.cash_entry,
                    self.wave_arrive_time_entry,
                    self.delay_entry,
                    self.path_index_entry,
                ]
            else:
                widget["spawn"] = [
                    self.cash_entry,
                    self.delay_entry,
                    self.path_index_entry,
                ]

            if index >= len(widget["spawn"]) - 1:
                self.add_monster()
                return "break"

        elif next_widget == "monster":
            widget["monster"] = [
                self.max_same_entry,
                self.max_entry,
                self.interval_entry,
                self.fixed_sub_path_entry,
                self.interval_next_entry,
            ]
            if index >= len(widget["monster"]) - 1:
                self.save_monster()
                return "break"

        self.entry_focus(widget[next_widget][index + 1])

        return "break"  # 阻止默认行为

    def entry_focus(self, entry):
        """聚焦输入框"""
        entry.focus()
        self.select_all_text(entry)

    def select_all_text(self, entry):
        """全选输入框内容"""
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)  # 将光标移到末尾


if __name__ == "__main__":
    root = tk.Tk()
    app = WaveDataGenerator(root)
    root.mainloop()
