from django import template
from django.http import QueryDict

register = template.Library()

@register.simple_tag
def query_string(get_params: QueryDict) -> str:
    """Return URL-encoded query-string for the given request.GET."""
    return get_params.urlencode()
