# core/decorators.py - ENHANCED with Quote System Security

"""
Enhanced decorators for authorization and access control including quote management.

These decorators act like intelligent security checkpoints that understand both
your existing permission system and the new quote workflow requirements.
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.urls import reverse
import logging

from .utils import (
    has_app_permission, has_role, is_employee, is_blogger, is_customer,
    can_access_admin, requires_gm_approval, log_security_event
)

logger = logging.getLogger('core.authentication')

# =====================================
# USER TYPE DECORATORS
# =====================================

def employee_required(view_func):
    """Require user to be an employee"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_employee(request.user):
            messages.error(request, "Employee access required.")
            log_security_event(
                user=request.user,
                event_type='access_denied',
                description='Non-employee attempted to access employee area',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def blogger_required(view_func):
    """Require user to be a blogger"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not is_blogger(request.user):
            messages.error(request, "Blogger access required.")
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def customer_required(view_func):
    """Require user to be a customer (or allow guest access for shopping)"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated and not is_customer(request.user):
            messages.error(request, "Customer access required.")
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    """Require admin-level access"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_access_admin(request.user):
            messages.error(request, "Administrator access required.")
            log_security_event(
                user=request.user,
                event_type='access_denied',
                description='Non-admin attempted to access admin area',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

# =====================================
# ROLE-BASED DECORATORS
# =====================================

def role_required(role_name):
    """Require specific employee role"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_role(request.user, role_name):
                messages.error(request, f"Role '{role_name}' required for this action.")
                log_security_event(
                    user=request.user,
                    event_type='access_denied',
                    description=f'User lacks required role: {role_name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def roles_required(*role_names):
    """Require any of the specified roles"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not any(has_role(request.user, role) for role in role_names):
                messages.error(request, f"One of these roles required: {', '.join(role_names)}")
                log_security_event(
                    user=request.user,
                    event_type='access_denied',
                    description=f'User lacks any required roles: {role_names}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# =====================================
# PERMISSION-BASED DECORATORS
# =====================================

def app_permission_required(app_name, required_level='view'):
    """Require specific app permission level"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_app_permission(request.user, app_name, required_level):  # Updated function name
                messages.error(request, f"Permission required: {app_name} ({required_level})")
                log_security_event(
                    user=request.user,
                    event_type='access_denied',
                    description=f'User lacks {required_level} permission for {app_name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                return redirect('core:dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def crm_permission_required(level='view'):
    """Shortcut for CRM permissions"""
    return app_permission_required('crm', level)

def inventory_permission_required(level='view'):
    """Shortcut for inventory permissions"""
    return app_permission_required('inventory', level)

def shop_admin_required(level='edit'):
    """Shortcut for shop management permissions"""
    return app_permission_required('shop', level)

def financial_permission_required(level='view'):
    """Shortcut for financial data permissions"""
    return app_permission_required('financial', level)

def quotes_permission_required(level='view'):
    """Shortcut for quotes permissions"""
    return app_permission_required('quotes', level)

def website_permission_required(level='view'):
    """Shortcut for website management permissions"""
    return app_permission_required('website', level)

# =====================================
# AJAX & API DECORATORS
# =====================================

def ajax_required(view_func):
    """Require AJAX request"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'AJAX request required'}, status=400)
        return view_func(request, *args, **kwargs)
    return wrapper

def ajax_employee_required(view_func):
    """Require employee access for AJAX requests"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'AJAX request required'}, status=400)
        
        if not is_employee(request.user):
            return JsonResponse({'error': 'Employee access required'}, status=403)
        
        return view_func(request, *args, **kwargs)
    return wrapper

def ajax_permission_required(app_name, required_level='view'):
    """Require specific permission for AJAX requests"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'AJAX request required'}, status=400)
            
            if not has_app_permission(request.user, app_name, required_level):
                return JsonResponse({
                    'error': f'Permission required: {app_name} ({required_level})'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# =====================================
# APPROVAL DECORATORS
# =====================================

def gm_approval_required(view_func):
    """Require GM approval for sensitive operations"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if requires_gm_approval(request.user):
            # In a real implementation, you might redirect to an approval request page
            # For now, we'll just check if there's a bypass parameter or session flag
            if not request.session.get('gm_approval_granted', False):
                messages.warning(request, "This action requires GM approval. Please contact your manager.")
                log_security_event(
                    user=request.user,
                    event_type='approval_required',
                    description='Action blocked - GM approval required',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                return redirect('core:request_approval')
        
        return view_func(request, *args, **kwargs)
    return wrapper

# =====================================
# SECURITY DECORATORS
# =====================================

def secure_view(view_func):
    """Add extra security logging to sensitive views"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        # Log access to secure view
        log_security_event(
            user=request.user,
            event_type='secure_access',
            description=f'Access to secure view: {view_func.__name__}',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            additional_data={
                'view_name': view_func.__name__,
                'url_path': request.path,
                'method': request.method
            }
        )
        
        return view_func(request, *args, **kwargs)
    return wrapper

def rate_limited(max_requests=10, time_window=60):
    """Simple rate limiting decorator"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            
            # Create a unique key for this user and view
            cache_key = f'rate_limit:{request.user.id if request.user.is_authenticated else request.META.get("REMOTE_ADDR")}:{view_func.__name__}'
            
            # Get current request count
            current_requests = cache.get(cache_key, 0)
            
            if current_requests >= max_requests:
                log_security_event(
                    user=request.user if request.user.is_authenticated else None,
                    event_type='rate_limit_exceeded',
                    description=f'Rate limit exceeded for view: {view_func.__name__}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': 'Rate limit exceeded'}, status=429)
                else:
                    messages.error(request, "Too many requests. Please try again later.")
                    return redirect('core:dashboard')
            
            # Increment counter
            cache.set(cache_key, current_requests + 1, timeout=time_window)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# =====================================
# COMPOSITE DECORATORS
# =====================================

def crm_view_required(view_func):
    """Common decorator for CRM views"""
    @wraps(view_func)
    @employee_required
    @crm_permission_required('view')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

def crm_edit_required(view_func):
    """Common decorator for CRM edit views"""
    @wraps(view_func)
    @employee_required
    @crm_permission_required('edit')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

def crm_admin_required(view_func):
    """Common decorator for CRM admin views"""
    @wraps(view_func)
    @employee_required
    @crm_permission_required('admin')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

def inventory_view_required(view_func):
    """Common decorator for inventory views"""
    @wraps(view_func)
    @employee_required
    @inventory_permission_required('view')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

def inventory_edit_required(view_func):
    """Common decorator for inventory edit views"""
    @wraps(view_func)
    @employee_required
    @inventory_permission_required('edit')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

def manager_required(view_func):
    """Require manager-level access (Sales Manager or higher)"""
    @wraps(view_func)
    @roles_required('sales_manager', 'business_owner', 'system_admin')
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

# =====================================
# CLASS-BASED VIEW MIXINS
# =====================================

class EmployeeRequiredMixin:
    """Mixin for class-based views requiring employee access"""
    
    def dispatch(self, request, *args, **kwargs):
        if not is_employee(request.user):
            messages.error(request, "Employee access required.")
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

class PermissionRequiredMixin:
    """Mixin for class-based views requiring specific permissions"""
    required_app = None
    required_level = 'view'
    
    def dispatch(self, request, *args, **kwargs):
        if not has_app_permission(request.user, self.required_app, self.required_level):
            messages.error(request, f"Permission required: {self.required_app} ({self.required_level})")
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

class RoleRequiredMixin:
    """Mixin for class-based views requiring specific roles"""
    required_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        if not any(has_role(request.user, role) for role in self.required_roles):
            messages.error(request, f"Required role: {', '.join(self.required_roles)}")
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

# =====================================
# UTILITY DECORATORS
# =====================================

def handle_permission_denied(view_func):
    """Handle permission denied gracefully"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except PermissionDenied as e:
            messages.error(request, str(e) if str(e) else "Permission denied.")
            log_security_event(
                user=request.user if request.user.is_authenticated else None,
                event_type='permission_denied',
                description=f'Permission denied in view: {view_func.__name__}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            return redirect('core:dashboard')
    return wrapper

def log_user_action(action_name):
    """Log user actions for audit trail"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Log the action
            log_security_event(
                user=request.user if request.user.is_authenticated else None,
                event_type='user_action',
                description=f'User action: {action_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                additional_data={
                    'action': action_name,
                    'view': view_func.__name__,
                    'method': request.method,
                    'path': request.path
                }
            )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def user_type_required(user_types, redirect_url='core:dashboard'):
    """
    Enhanced decorator to check if a user has the required user type.
    Now supports the new sales roles while maintaining backward compatibility.
    
    Args:
        user_types: List or single string of user types allowed to access this view
        redirect_url: URL to redirect to if permission is denied
        
    Usage:
        @user_type_required(['sales_manager', 'blitzhub_admin'])
        def approve_quote(request):
            # Only managers and admins can access this view
    """
    if isinstance(user_types, str):
        user_types = [user_types]
        
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Authentication required',
                        'redirect': reverse('core:login')
                    }, status=401)
                return redirect('core:login')
                
            if not hasattr(request.user, 'profile'):
                logger.warning(f"User {request.user.username} has no profile while accessing a protected view")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'User profile missing',
                        'redirect': redirect_url
                    }, status=403)
                
                messages.warning(request, 'Your user profile is missing or incomplete.')
                return redirect(redirect_url)
                
            user_type = request.user.profile.user_type
            
            if user_type not in user_types:
                logger.warning(
                    f"User type restriction: User {request.user.username} with type {user_type} "
                    f"attempted to access a view restricted to {user_types}"
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Insufficient user role',
                        'redirect': redirect_url
                    }, status=403)
                
                messages.warning(request, 'You do not have the required role to access this area.')
                return redirect(redirect_url)
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def password_expiration_check(view_func):
    """
    Enhanced decorator to check if the user's password has expired.
    Includes special handling for quote-related workflows.
    
    Usage:
        @password_expiration_check
        def quote_dashboard(request):
            # User's password is guaranteed to be current
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        from django.utils import timezone
        from django.conf import settings
        
        # Skip if user is not authenticated
        if not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
            
        # Skip for password change view to avoid redirect loop
        if request.resolver_match.url_name == 'password_change':
            return view_func(request, *args, **kwargs)
        
        # Skip for AJAX requests from quote builder to avoid disrupting workflow
        if (request.headers.get('X-Requested-With') == 'XMLHttpRequest' and 
            'quote' in request.path):
            return view_func(request, *args, **kwargs)
            
        # Get password expiration settings
        password_expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', None)
        
        if password_expiry_days and hasattr(request.user, 'profile'):
            # Use last_password_change from profile, or fallback to date_joined if not set
            last_change = getattr(request.user, 'last_password_change', request.user.date_joined)
            days_since_change = (timezone.now() - last_change).days
            
            if days_since_change >= password_expiry_days:
                logger.info(f"Password expired for user {request.user.username}")
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Password expired',
                        'redirect': reverse('core:password_change')
                    }, status=403)
                
                messages.warning(
                    request, 
                    f"Your password has expired. It must be changed every {password_expiry_days} days for security reasons."
                )
                return redirect('core:password_change')
                
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def quote_access_required(permission_level='view'):
    """
    Specialized decorator for quote-specific access control.
    
    This decorator not only checks quote permissions but also handles quote-specific
    business rules like ownership validation and status-based access control.
    
    Args:
        permission_level: Minimum permission level required for quotes
        
    Usage:
        @quote_access_required('edit')
        def edit_quote(request, quote_id):
            # User has quote edit permissions and can access this specific quote
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Additional quote-specific logic
            quote_id = kwargs.get('quote_id') or kwargs.get('pk')
            
            if quote_id and not request.user.profile.is_admin:
                try:
                    from quotes.models import Quote
                    quote = Quote.objects.get(id=quote_id)
                    
                    # Check if user has access to this specific quote
                    has_access = (
                        quote.created_by == request.user or 
                        quote.assigned_to == request.user or
                        request.user.profile.is_admin
                    )
                    
                    if not has_access:
                        logger.warning(
                            f"Quote access denied: User {request.user.username} "
                            f"attempted to access quote {quote_id} they don't own"
                        )
                        
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': 'You do not have access to this quote'
                            }, status=403)
                        
                        messages.error(request, 'You do not have access to this quote.')
                        return redirect('quotes:quote_list')
                    
                    # Check if quote can be edited based on status
                    if permission_level in ['edit', 'admin']:
                        if quote.status in ['accepted', 'converted', 'cancelled']:
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'error': f'Quote cannot be edited in {quote.get_status_display()} status'
                                }, status=400)
                            
                            messages.warning(
                                request, 
                                f'Quote {quote.quote_number} cannot be edited because it is {quote.get_status_display()}'
                            )
                            return redirect('quotes:quote_detail', quote_id=quote.id)
                        
                except Quote.DoesNotExist:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Quote not found'
                        }, status=404)
                    
                    messages.error(request, 'Quote not found.')
                    return redirect('quotes:quote_list')
                except Exception as e:
                    logger.error(f"Error in quote access check: {str(e)}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'An error occurred while checking quote access'
                        }, status=500)
                    
                    messages.error(request, 'An error occurred. Please try again.')
                    return redirect('quotes:quote_list')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def sales_team_required(view_func):
    """
    Decorator specifically for sales team members (sales reps and managers).
    
    This creates a clear distinction between general employees and sales-focused roles,
    which is important for quote management workflows.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile'):
            logger.warning(f"User {request.user.username} has no profile while accessing sales area")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'User profile missing',
                    'redirect': reverse('core:dashboard')
                }, status=403)
            
            messages.warning(request, 'Your user profile is missing or incomplete.')
            return redirect('core:dashboard')
        
        if not request.user.profile.user_type in ['sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin']:
            logger.warning(
                f"Non-sales user {request.user.username} attempted to access sales area"
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Sales team access required',
                    'redirect': reverse('core:dashboard')
                }, status=403)
            
            messages.warning(request, 'This area is restricted to sales team members.')
            return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def quote_approval_required(view_func):
    """
    Decorator for operations that require quote approval authority.
    
    Only sales managers and admins can approve quotes, especially high-value
    or high-discount quotes that exceed business thresholds.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.profile.can_approve_quotes:
            logger.warning(
                f"User {request.user.username} attempted quote approval without authority"
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Quote approval authority required',
                    'redirect': reverse('quotes:quote_list')
                }, status=403)
            
            messages.error(request, 'You do not have authority to approve quotes.')
            return redirect('quotes:quote_list')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def quote_status_validation(allowed_statuses):
    """
    Decorator to validate quote status before allowing operations.
    
    This ensures that certain operations (like editing) can only happen
    when quotes are in appropriate statuses.
    
    Args:
        allowed_statuses: List of statuses that allow this operation
        
    Usage:
        @quote_status_validation(['draft', 'sent'])
        def edit_quote_items(request, quote_id):
            # Quote is guaranteed to be in draft or sent status
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            quote_id = kwargs.get('quote_id') or kwargs.get('pk')
            
            if quote_id:
                try:
                    from quotes.models import Quote
                    quote = Quote.objects.get(id=quote_id)
                    
                    if quote.status not in allowed_statuses:
                        error_message = (
                            f"Operation not allowed for quote in {quote.get_status_display()} status. "
                            f"Allowed statuses: {', '.join(allowed_statuses)}"
                        )
                        
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'error': error_message
                            }, status=400)
                        
                        messages.error(request, error_message)
                        return redirect('quotes:quote_detail', quote_id=quote.id)
                        
                except Quote.DoesNotExist:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Quote not found'
                        }, status=404)
                    
                    messages.error(request, 'Quote not found.')
                    return redirect('quotes:quote_list')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def quote_edit_required(view_func):
    """Shortcut decorator for views that require quote editing permissions"""
    return quote_access_required('edit')(view_func)

def quote_admin_required(view_func):
    """Shortcut decorator for views that require quote admin permissions"""
    return quote_access_required('admin')(view_func)

def draft_or_sent_required(view_func):
    """Shortcut decorator for operations only allowed on draft or sent quotes"""
    return quote_status_validation(['draft', 'sent'])(view_func)

def editable_quote_required(view_func):
    """Shortcut decorator for operations requiring editable quote status"""
    return quote_status_validation(['draft', 'sent', 'viewed'])(view_func)
