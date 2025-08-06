# core/templatetags/core_extras.py
from django import template

register = template.Library()

@register.filter
def format_field_name(value):
    """
    Format field names by replacing underscores with spaces and title casing
    Usage: {{ field_name|format_field_name }}
    """
    if not value:
        return value
    
    # Replace underscores with spaces and title case
    return str(value).replace('_', ' ').title()