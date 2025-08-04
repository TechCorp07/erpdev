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
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

def permission_required(app_name, permission_level='view'):
    """
    Enhanced decorator to check if a user has the required permission level for an app.
    
    This decorator now fully supports the quote system while maintaining backward
    compatibility with your existing CRM and inventory permissions.
    
    Args:
        app_name: The name of the app to check permissions for ('quotes', 'crm', 'inventory', etc.)
        permission_level: Minimum permission level required ('view', 'edit', 'admin')
        
    Usage:
        @permission_required('quotes', 'edit')
        def create_quote(request):
            # User is guaranteed to have quote edit permissions here
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            from .utils import check_app_permission
            
            if not request.user.is_authenticated:
                # Handle AJAX requests differently from regular requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Authentication required',
                        'redirect': reverse('core:login')
                    }, status=401)
                return redirect('core:login')
                
            has_permission = check_app_permission(request.user, app_name, permission_level)
            
            if not has_permission:
                logger.warning(
                    f"Permission denied: User {request.user.username} attempted to access {app_name} "
                    f"with insufficient privileges (required: {permission_level})"
                )
                
                # Handle AJAX requests with JSON response
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f'You do not have {permission_level} access to {app_name.upper()}',
                        'redirect': reverse('core:dashboard')
                    }, status=403)
                
                # Handle regular requests with message and redirect
                messages.warning(
                    request, 
                    f"You don't have sufficient permissions to access this area. "
                    f"Required permission: {permission_level} access for {app_name}."
                )
                return redirect('core:dashboard')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

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
        @permission_required('quotes', permission_level)  # Uses your existing decorator
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
    @permission_required('quotes', 'admin')
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

def ajax_required(view_func):
    """
    Enhanced decorator to ensure a view is only accessed via AJAX request.
    Provides better error messages for non-AJAX attempts.
    
    Usage:
        @ajax_required
        def update_quote_item(request):
            # This view can only be accessed via AJAX
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            logger.warning(f"Non-AJAX request rejected for {view_func.__name__}")
            
            # Return appropriate response based on request type
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': False,
                    'error': 'This endpoint requires AJAX request'
                }, status=400)
            else:
                return HttpResponseForbidden("This view can only be accessed via AJAX")
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

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

# Convenience decorators for common quote operations
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
