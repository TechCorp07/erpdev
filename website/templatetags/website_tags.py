"""
Custom template tags and filters for the website app
"""
from django import template
from django.utils.safestring import mark_safe
import markdown
import re

register = template.Library()

@register.filter(name='markdownify')
def markdownify(text):
    """
    Convert markdown text to HTML
    """
    return mark_safe(markdown.markdown(text))

@register.filter(name='truncate_smart')
def truncate_smart(value, limit=80):
    """
    Truncates a string after a given number of chars 
    maintaining whole words.
    """
    if len(value) <= limit:
        return value
    
    # Find the last space within the limit
    truncd = value[:limit]
    if ' ' in truncd:
        truncd = truncd.rsplit(' ', 1)[0]
    
    return truncd + '...'

@register.simple_tag
def active_link(request, view_name):
    """
    Returns 'active' if the current URL matches the view_name
    Useful for highlighting active nav links
    """
    from django.urls import resolve, Resolver404
    
    try:
        return 'active' if resolve(request.path_info).url_name == view_name else ''
    except Resolver404:
        return ''

@register.inclusion_tag('website/includes/social_share.html')
def social_share(url, title):
    """
    Renders social sharing buttons for the given URL and title
    """
    return {
        'url': url,
        'title': title
    }

@register.inclusion_tag('website/includes/pagination.html')
def pagination(page_obj, query_params=None):
    """
    Renders pagination controls for the given page object
    Preserves any query parameters from the URL
    """
    return {
        'page_obj': page_obj,
        'query_params': query_params or {}
    }