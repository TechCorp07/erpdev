# In templatetags/dict_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def query_replace(request_get, param):
    """
    Removes a parameter from request.GET.
    Usage: {{ request.GET|query_replace:'sort' }}
    """
    get_dict = request_get.copy()
    if param in get_dict:
        del get_dict[param]
    return get_dict.urlencode()
