# core/templatetags/core_extras.py
from django import template
from django.contrib.auth.models import User
from core.utils import (
    has_app_permission as utils_has_app_permission, get_user_permissions, can_user_manage_roles,
    is_employee, is_admin_user, is_manager_user
)

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

@register.filter
def has_app_access(user, app_name):
    """
    Template filter to check if user has any access to an app.
    Usage: {% if user|has_app_access:'crm' %}
    """
    if not user or not user.is_authenticated:
        return False
    return utils_has_app_permission(user, app_name, 'view')

@register.filter
def has_app_permission_level(user, app_and_level):
    """
    Template filter to check if user has specific permission level.
    Usage: {% if user|has_app_permission_level:'crm:edit' %}
    """
    if not user or not user.is_authenticated:
        return False
    
    if ':' in app_and_level:
        app_name, level = app_and_level.split(':')
        return utils_has_app_permission(user, app_name, level)
    else:
        # Default to view level if no level specified
        return utils_has_app_permission(user, app_and_level, 'view')

@register.filter
def get_app_permission(user, app_name):
    """
    Template filter to get user's permission level for an app.
    Usage: {{ user|get_app_permission:'crm' }}
    Returns: 'admin', 'edit', 'view', or None
    """
    if not user or not user.is_authenticated:
        return None
    
    permissions = get_user_permissions(user)
    return permissions.get(app_name)

@register.filter
def can_manage_users(user):
    """
    Template filter to check if user can manage other users.
    Usage: {% if user|can_manage_users %}
    """
    if not user or not user.is_authenticated:
        return False
    return can_user_manage_roles(user)

@register.filter
def is_system_admin(user):
    """
    Template filter to check if user is a system administrator.
    Usage: {% if user|is_system_admin %}
    """
    if not user or not user.is_authenticated:
        return False
    return is_admin_user(user)

@register.filter
def is_manager(user):
    """
    Template filter to check if user is a manager.
    Usage: {% if user|is_manager %}
    """
    if not user or not user.is_authenticated:
        return False
    return is_manager_user(user)

@register.filter
def is_employee_user(user):
    """
    Template filter to check if user is an employee.
    Usage: {% if user|is_employee_user %}
    """
    if not user or not user.is_authenticated:
        return False
    return is_employee(user)

@register.simple_tag
def get_user_app_permissions(user):
    """
    Template tag to get all user permissions as a dictionary.
    Usage: {% get_user_app_permissions user as permissions %}
    """
    if not user or not user.is_authenticated:
        return {}
    return get_user_permissions(user)

@register.inclusion_tag('core/fragments/permission_badge.html')
def permission_badge(user, app_name):
    """
    Template tag to render a permission level badge.
    Usage: {% permission_badge user 'crm' %}
    """
    permission_level = get_app_permission(user, app_name)
    
    badge_config = {
        'admin': {'class': 'bg-success', 'text': 'Admin'},
        'edit': {'class': 'bg-primary', 'text': 'Edit'},
        'view': {'class': 'bg-secondary', 'text': 'View'},
    }
    
    return {
        'permission_level': permission_level,
        'badge_config': badge_config.get(permission_level, {}),
        'show_badge': permission_level is not None
    }

@register.filter
def user_role_display(user):
    """
    Template filter to get a user-friendly role display name.
    Usage: {{ user|user_role_display }}
    """
    if not user or not user.is_authenticated:
        return 'Guest'
    
    if not hasattr(user, 'profile'):
        return 'User'
    
    profile = user.profile
    
    # Check for admin status first
    if user.is_superuser:
        return 'Super Administrator'
    elif is_admin_user(user):
        return 'Administrator'
    elif is_manager_user(user):
        return 'Manager'
    
    # Return user type with department if available
    user_type = profile.get_user_type_display()
    if profile.user_type == 'employee' and profile.department:
        dept_display = profile.get_department_display()
        return f'{user_type} - {dept_display}'
    
    return user_type

@register.filter
def has_any_management_access(user):
    """
    Check if user has access to any management features.
    Usage: {% if user|has_any_management_access %}
    """
    if not user or not user.is_authenticated:
        return False
    
    # Check if user can manage users or has admin access to any app
    if can_user_manage_roles(user):
        return True
    
    # Check if user has admin access to any app
    permissions = get_user_permissions(user)
    return any(level == 'admin' for level in permissions.values())

@register.simple_tag(takes_context=True)
def nav_active(context, *url_names):
    """
    Template tag to check if current URL matches any of the provided names.
    Usage: {% nav_active 'crm:dashboard' 'crm:list' as active %}{% if active %}active{% endif %}
    """
    request = context.get('request')
    if not request:
        return False
    
    current_url_name = None
    if hasattr(request, 'resolver_match') and request.resolver_match:
        current_url_name = request.resolver_match.url_name
        current_namespace = request.resolver_match.namespace
        if current_namespace:
            current_full_name = f"{current_namespace}:{current_url_name}"
        else:
            current_full_name = current_url_name
    
    for url_name in url_names:
        if url_name == current_url_name or url_name == current_full_name:
            return True
        # Check for wildcard matches
        if '*' in url_name:
            pattern = url_name.replace('*', '')
            if current_full_name and current_full_name.startswith(pattern):
                return True
    
    return False
