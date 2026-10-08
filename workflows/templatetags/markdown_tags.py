from django import template

from workflows.utils import render_markdown


register = template.Library()


@register.filter(is_safe=True)
def markdown(value):
    return render_markdown(value)
