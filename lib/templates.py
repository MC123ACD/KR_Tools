from jinja2 import Template, Environment, FileSystemLoader

# 正确配置环境
env = Environment(
    loader=FileSystemLoader("lib"),  # 指定模板目录
)

write_waves_data_template = env.from_string(
    """{%- from "templates_macros" import add_comma -%}
    return {
    cash = {{cash}},
    groups = {
        {%- for wave in groups %}
        {
            interval = {{wave["wave_interval"]}},
            waves = {
                {%- for spawns in wave["spawns"] %}
                {
                    {%- if spawns.get("some_flying") %}
                    some_flying = spawns["some_flying"]
                    {%- endif %}
                    delay = {{spawns["delay"]}},
                    path_index = {{spawns["path_index"]}},
                    spawns = {
                        {%- for spawn in spawns["spawns"] %}
                        {
                            {%- if spawn.get("creep_aux") %}
                            creep_aux = spawn["creep_aux"],
                            {%- endif %}
                            creep = "{{spawn["creep"]}}",
                            interval = {{spawn["interval"]}},
                            max = {{spawn["max"]}},
                            max_same = {{spawn["max_same"]}},
                            fixed_sub_path = {{ 1 if spawn["subpath"] else 0 }},
                            path = {{spawn["subpath"]}}
                            interval_next = {{spawn["interval_next"]}}
                        }{{add_comma(loop.last)}}
                        {%- endfor %}
                    }
                }{{add_comma(loop.last)}}
                {%- endfor %}
            }
        }{{add_comma(loop.last)}}
        {%- endfor %}
    }
}
"""
)

write_dove_spawns_criket_data_template = env.from_string(
    """{%- from "templates_macros" import add_comma -%}
    on = true,
    cash = {{cash}},
    gold_base = {{cash}},
    gold_judge = false,
    fps_transformed = false,
    groups = {
        {%- for group in groups %}
        {
            {%- if spawns.get("some_flying") %}
            some_flying = spawns["some_flying"],
            {%- endif %}
            delay = {{spawns["delay"]}},
            path_index = {{spawns["path_index"]}}
            spawns = {
                {%- for spawn in spawns["spawns"] %}
                {
                    {%- if spawn.get("creep_aux") %}
                    creep_aux = spawn["creep_aux"],
                    {%- endif %}
                    creep = "{{spawn["creep"]}}",
                    interval = {{spawn["interval"]}},
                    max = {{spawn["max"]}},
                    max_same = {{spawn["max_same"]}},
                    fixed_sub_path = {{spawn["fixed_sub_path"]}},
                    path = {{spawn["path"]}},
                    interval_next = {{spawn["interval_next"]}}
                }{{add_comma(loop.last)}}
                {%- endfor %}
            }
        }{{add_comma(loop.last)}}
        {%- endfor %}
    }
    required_sounds = {},
    required_textures = {
        "go_enemies_ancient_metropolis",
        "go_enemies_bandits",
        "go_enemies_bittering_rancor",
        "go_enemies_blackburn",
        "go_enemies_desert",
        "go_enemies_elven_woods",
        "go_enemies_faerie_grove",
        "go_enemies_forgotten_treasures",
        "go_enemies_grass",
        "go_enemies_halloween",
        "go_enemies_hulking_rage",
        "go_enemies_ice",
        "go_enemies_jungle",
        "go_enemies_mactans_malicia",
        "go_enemies_rising_tides",
        "go_enemies_rotten",
        "go_enemies_sarelgaz",
        "go_enemies_storm",
        "go_enemies_torment",
        "go_enemies_underground",
        "go_enemies_wastelands"
    }
}
"""
)
