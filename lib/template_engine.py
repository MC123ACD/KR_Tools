from jinja2 import Template

write_waves_data_template = Template(
"""
return {
    cash = {{cash}},
    groups = {
        {% for wave in groups %}

        {% endfor %}
    }
"""
)
