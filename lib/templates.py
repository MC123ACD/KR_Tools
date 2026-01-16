from jinja2 import Template, Environment, FileSystemLoader
from lib.utils import key_to_lua, value_to_lua

# 正确配置环境
env = Environment(
    loader=FileSystemLoader("lib"),  # 指定模板目录
)
env.globals["key_to_lua"] = key_to_lua
env.globals["value_to_lua"] = value_to_lua

write_waves_data_template = env.from_string(
    """return {
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
                            creep_aux = "{{spawn["creep_aux"]}}",
                            {%- endif %}
                            creep = "{{spawn["creep"]}}",
                            interval = {{spawn["interval"]}},
                            max = {{spawn["max"]}},
                            max_same = {{spawn["max_same"]}},
                            fixed_sub_path = {{ 1 if spawn["subpath"] else 0 }},
                            path = {{spawn["subpath"]}},
                            interval_next = {{spawn["interval_next"]}}
                        }{%- if not loop.last %},{% endif -%}
                        {%- endfor %}
                    }
                }{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            }
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
}"""
)

write_dove_spawns_criket_data_template = env.from_string(
"""return {
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
            path_index = {{spawns["path_index"]}},
            spawns = {
                {%- for spawn in spawns["spawns"] %}
                {
                    {%- if spawn.get("creep_aux") %}
                    creep_aux = "{{spawn["creep_aux"]}}",
                    {%- endif %}
                    creep = "{{spawn["creep"]}}",
                    interval = {{spawn["interval"]}},
                    max = {{spawn["max"]}},
                    max_same = {{spawn["max_same"]}},
                    fixed_sub_path = {{ 1 if spawn["subpath"] else 0 }},
                    path = {{spawn["subpath"]}},
                    interval_next = {{spawn["interval_next"]}}
                }{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            }
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
    required_sounds = {},
    required_textures = {
        {%- for texture in required_textures %}
        "{{texture}}"{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
}"""
)


write_spawners_data_template = env.from_string(
"""return {
    groups = {
        {%- for group in groups %}
        {{key_to_lua(group[0])}} = {
            {%- for i in group[1] %}
            {{value_to_lua(i)}}{%- if not loop.last %},{% endif -%}
            {%- endfor %}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    points = {
        {%- for point in points %}
        {
            path = {{point["path"]}},
            from = {
                x = {{point["from"]["x"]}},
                y = {{point["from"]["y"]}}
            },
            to = {
                x = {{point["to"]["x"]}},
                y = {{point["to"]["y"]}}
            }
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    waves = {
        {
            {%- for wave_idx, wave_data in waves.items() %}
            {{key_to_lua(wave_idx)}} = {
                {%- for entries in wave_data %}
                {
                    {%- for entrie in entries %}
                    {{value_to_lua(entrie)}}{%- if not loop.last %},{% endif -%}
                    {%- endfor %}
                }{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            }{%- if not loop.last %},{% endif -%}
            {%- endfor %}
        }
    }
}
"""
)

write_common_animations_data_template = env.from_string(
"""return {
    {%- for name, anim_data in animations_data.items() %}
    {{name}} = {
        {%- if anim_data["is_layer"] %}
        layer_prefix = "{{anim_data["layer_prefix"]}}",
        layer_to = {{anim_data["layer_to"]}},
        layer_from = {{anim_data["layer_from"]}},
        {%- else %}
        prefix = "{{anim_data["prefix"]}}",
        {%- endif %}
        to = {{anim_data["to"]}},
        from = {{anim_data["from"]}}
    }{%- if not loop.last %},{% endif -%}
    {%- endfor %}
}"""
)

write_exos_animations_data_template = env.from_string(
"""return {
    fps = {{fps}},
    partScaleCompensation = {{partScaleCompensation}},
    animations = {
        {%- for anim in animations %}
        {
            name = "{{anim["name"]}}",
            frames = {
                {%- for af in anim["frames"] %}
                {
                    parts = {
                        {%- for p in af["parts"] %}
                        {
                            name = "{{p["name"]}}",
                            {%- if p.get("alpha") %}
                            alpha = {{p["alpha"]}}
                            {% endif -%}
                            {% set xform = p["xform"] %}
                            xform = {
                                sx = {{xform["sx"]}},
                                sy = {{xform["sy"]}},
                                kx = {{xform["kx"]}},
                                ky = {{xform["ky"]}},
                                x = {{xform["x"]}},
                                y = {{xform["y"]}},
                                r = {{xform["r"]}}
                            }
                        }{%- if not loop.last %},{% endif -%}
                        {%- endfor %}
                    }
                }{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            }
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    parts = {
        {%- for name, part in parts.items() %}
        {{name}} = {
            name = "{{part["name"]}}",
            offsetX = {{part["offsetX"]}},
            offsetY = {{part["offsetY"]}}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
}"""
)

write_level_data_template = env.from_string(
"""return {
    level_terrain_type = {{terrain_type}},
    locked_hero = false,
    max_upgrade_level = 5,
    custom_start_pos = {
        zoom = 1.3,
        pos = {
            x = 512,
            y = 384
        }
    },
    level_mode_overrides = {},
    custom_spawn_pos = {
        {%- for pos in hero_positions %}
        {
            pos = {
                x = {{pos.get("x", 0)}},
                y = {{pos.get("y", 0)}}
            }
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    entities_list = {
        {%- for entity in entities_list %}
        {
            {%- for key, value in entity.items() %}
            {%- if value is mapping %}
            {{key_to_lua(key)}} = {
                x = {{value.get("x", 0)}},
                y = {{value.get("y", 0)}}
            }{%- if not loop.last %},{% endif -%}
            {%- else %}
            {{key_to_lua(key)}} = {{value_to_lua(value)}}{%- if not loop.last %},{% endif -%}
            {% endif -%}
            {%- endfor %}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    nav_mesh = {
        {%- for mesh in nav_mesh %}
        {
            {%- for v in mesh %}
            {{v}}{%- if not loop.last %},{% endif -%}
            {%- endfor %}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    {%- if invalid_path_ranges %}
    invalid_path_ranges = {
        {%- for invalid_range in invalid_path_ranges %}
        {
            form = {{invalid_range["from"]}},
            to = {{invalid_range["to"]}},
            path_id = {{invalid_range["path_id"]}}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    {%- else %}
    invalid_path_ranges = {},
    {% endif -%}
    required_exoskeletons = {},
    required_sounds = {},
    required_textures = {
        {%- for texture in required_textures %}
        "{{texture}}"{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
}
"""
)

write_paths_data_template = env.from_string(
"""return {
    active = {
        {%- for active in active_paths %}
        {{value_to_lua(active)}}{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    connections = {},
    paths = {
        {%- for path in paths %}
        {
            {%- for subpath in path %}
            {
                {%- for point in subpath %}
                {
                    x = {{point["x"]}},
                    y = {{point["y"]}}
                }{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            }{%- if not loop.last %},{% endif -%}
            {%- endfor %}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    },
    curves = {
        {%- for curve in curves %}
        {
            nodes = {
                {%- for node in curve["nodes"] %}
                {
                    x = {{node["x"]}},
                    y = {{node["y"]}}
                }{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            },
            widths = {
                {%- for w in curve["widths"] %}
                {{w}}{%- if not loop.last %},{% endif -%}
                {%- endfor %}
            }
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
}"""
)

write_grids_data_template = env.from_string(
"""return {
    ox = {{ox}},
    oy = {{oy}},
    cell_size = {{cell_size}},
    grid = {
        {%- for column in grid %}
        {
            {%- for row_d in column %}
            {{row_d}}{%- if not loop.last %},{% endif -%}
            {%- endfor %}
        }{%- if not loop.last %},{% endif -%}
        {%- endfor %}
    }
}"""
)
