from django import template
import builtins

register = template.Library()

@register.filter
def zip(a, b):
    """{{ list1|zip:list2 }} → iterable of tuples"""
    return zip(a, b)

@register.filter(name="zip_lists")
def zip_lists(a, b):
    return builtins.zip(a, b)
