import json
import re
from jinja2 import Environment


# def json_with_trailing_commas(template_str):
#     # 移除对象和数组末尾的逗号
#     template_str = re.sub(r",\s*}", "}", template_str)
#     template_str = re.sub(r",\s*\]", "]", template_str)
#     return template_str


env = Environment()
# env.filters["json_with_commas"] = json_with_trailing_commas

# 在模板中使用
template = env.from_string(
    """
{
    "name": "{{ name }}",
    "items": [
        {% for item in items %}
        "{{ item }}"{% if not loop.last %},{% endif %}
        {% endfor %}
    ],
    "metadata": {
        {% for key, value in metadata.items() %}
        "{{ key }}": "{{ value }}"{% if not loop.last %},{% endif %}
        {% endfor %}
    }
}
"""
)

data = {"name": "test", "items": ["a", "b", "c","d"], "metadata": {"x": 1, "y": 2}}

result = template.render(data)
print(result)
