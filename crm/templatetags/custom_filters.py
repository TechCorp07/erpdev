from django import template

register = template.Library()

@register.filter
def replace_underscore_with_space(value):
    """Replace underscores with spaces for display purposes."""
    if isinstance(value, str):
        return value.replace('_', ' ')
    return value
