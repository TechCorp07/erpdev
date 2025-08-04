"""
Security mixins for class-based views
"""
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
import logging

logger = logging.getLogger(__name__)

class UserTypeRequiredMixin(UserPassesTestMixin):
    """
    Mixin to restrict view access to specific user types
    
    Attributes:
        allowed_user_types (list): List of user types that can access this view
        permission_denied_message (str): Message shown when access is denied
        permission_denied_url (str): URL to redirect to when access is denied
    """
    allowed_user_types = []
    permission_denied_message = "You do not have the required role to access this page."
    permission_denied_url = 'core:dashboard'
    
    def test_func(self):
        user = self.request.user
        
        if not hasattr(user, 'profile'):
            return False
            
        return user.profile.user_type in self.allowed_user_types
    
    def handle_no_permission(self):
        messages.warning(self.request, self.permission_denied_message)
        return redirect(self.permission_denied_url)


class AppPermissionRequiredMixin(UserPassesTestMixin):
    """
    Mixin to restrict view access based on app permissions
    
    Attributes:
        required_app (str): The app that requires permission
        required_level (str): The minimum permission level needed (view, edit, admin)
        permission_denied_message (str): Message shown when access is denied
        permission_denied_url (str): URL to redirect to when access is denied
    """
    required_app = None
    required_level = 'view'
    permission_denied_message = "You do not have sufficient permissions to access this page."
    permission_denied_url = 'core:dashboard'
    
    def test_func(self):
        from .utils import check_app_permission
        
        user = self.request.user
        if not user.is_authenticated:
            return False
            
        return check_app_permission(user, self.required_app, self.required_level)
    
    def handle_no_permission(self):
        messages.warning(self.request, self.permission_denied_message)
        return redirect(self.permission_denied_url)


class PasswordExpirationMixin(LoginRequiredMixin):
    """
    Mixin to check if a user's password has expired and redirect to password change
    """
    def dispatch(self, request, *args, **kwargs):
        from .utils import is_password_expired
        
        # First check if user is authenticated
        if not request.user.is_authenticated:
            return self.handle_no_permission()
            
        # Only check password expiration for authenticated users
        if is_password_expired(request.user):
            # Skip for password change view to avoid redirect loop
            if request.resolver_match.url_name != 'password_change':
                from django.conf import settings
                expire_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
                
                messages.warning(
                    request, 
                    f"Your password has expired. For security reasons, "
                    f"passwords must be changed every {expire_days} days."
                )
                return redirect('core:password_change')
                
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(UserTypeRequiredMixin):
    """
    Mixin to restrict view access to admin users only
    """
    allowed_user_types = ['blitzhub_admin', 'it_admin']
    permission_denied_message = "This page is restricted to administrators only."


class ITAdminRequiredMixin(UserTypeRequiredMixin):
    """
    Mixin to restrict view access to IT admin users only
    """
    allowed_user_types = ['it_admin']
    permission_denied_message = "This page is restricted to IT administrators only."


class EmployeeRequiredMixin(UserTypeRequiredMixin):
    """
    Mixin to restrict view access to employees only
    """
    allowed_user_types = ['employee', 'blitzhub_admin', 'it_admin']
    permission_denied_message = "This page is restricted to employees only."
    permission_denied_url = 'website:home'  # Redirect to website home for non-employees
