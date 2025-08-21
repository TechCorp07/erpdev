# core/middleware.py - ENHANCED with Quote System Integration

"""
Enhanced middleware for comprehensive security and workflow management.

This middleware system provides intelligent access control that understands
both your existing permission structure and the new quote management workflows,
ensuring security while enabling smooth business operations.
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve, reverse
from django.conf import settings
from django.utils.module_loading import import_string
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)

class EmployeeAccessMiddleware:
    """
    Enhanced middleware to control access to protected areas with quote system support.
    
    This middleware now handles the complete business workflow including quote-specific
    access patterns while maintaining backward compatibility with existing systems.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Enhanced access rules from settings with quote system integration
        self.access_rules = getattr(settings, 'ACCESS_CONTROL_RULES', {})

    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Get the resolved URL
        try:
            resolver_match = resolve(request.path_info)
            app_name = resolver_match.app_name
            url_name = resolver_match.url_name
            
            # Skip for authentication views (login/logout)
            if self._is_auth_view(app_name, url_name):
                return None
            
            # Skip for public quote preview URLs (client portal)
            if self._is_public_quote_view(app_name, url_name, view_kwargs):
                return None
                
            # Get access rules for this view
            rule = self._get_access_rule(app_name, url_name)
            if not rule:
                return None  # No rules for this view
            
            # Check if authentication is required
            if rule.get('login_required', False) and not request.user.is_authenticated:
                login_url = rule.get('login_url') or f'{app_name}:login'
                logger.info(f"Unauthenticated user attempted to access {app_name}:{url_name}")
                
                # Handle AJAX requests appropriately
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': 'Authentication required',
                        'redirect': reverse('core:login')
                    }, status=401)
                
                return redirect(login_url)
            
            # Check user type restrictions
            if rule.get('user_types') and request.user.is_authenticated:
                if not hasattr(request.user, 'profile'):
                    logger.warning(f"User {request.user.username} has no profile while accessing {app_name}:{url_name}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'User profile missing',
                            'redirect': reverse('core:dashboard')
                        }, status=403)
                    
                    messages.warning(request, 'Your user profile is missing or incomplete.')
                    return redirect(rule.get('failure_url', 'website:home'))
                
                user_type = request.user.profile.user_type
                allowed_types = rule.get('user_types', [])
                
                if user_type not in allowed_types:
                    logger.warning(f"User {request.user.username} with type {user_type} attempted unauthorized access to {app_name}:{url_name}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': 'Insufficient permissions',
                            'redirect': reverse('core:dashboard')
                        }, status=403)
                    
                    messages.warning(request, rule.get('access_denied_message', 'You do not have access to this area.'))
                    return redirect(rule.get('failure_url', 'website:home'))
            
            # Check application-specific permissions
            if rule.get('app_permission') and request.user.is_authenticated:
                app_name_perm = rule['app_permission'].get('app')
                required_level = rule['app_permission'].get('level', 'view')
                
                # Updated import and function call
                from .utils import has_app_permission
                if not has_app_permission(request.user, app_name_perm, required_level):
                    logger.warning(
                        f"User {request.user.username} lacks {required_level} permission for {app_name_perm} "
                        f"while accessing {app_name}:{url_name}"
                    )
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': f'Insufficient {app_name_perm} permissions',
                            'redirect': reverse('core:dashboard')
                        }, status=403)
                    
                    messages.warning(
                        request, 
                        f'You do not have {required_level} access to {app_name_perm.upper()}.'
                    )
                    return redirect(rule.get('failure_url', 'core:dashboard'))
            
            # Check quote-specific access rules
            if app_name == 'quotes' and request.user.is_authenticated:
                quote_access_result = self._check_quote_specific_access(request, url_name, view_kwargs)
                if quote_access_result:
                    return quote_access_result
            
            # Check additional access checks if defined
            access_check = rule.get('access_check')
            if access_check and request.user.is_authenticated:
                if isinstance(access_check, str):
                    try:
                        check_func = import_string(access_check)
                        
                        # Get access_check_args if available
                        access_check_args = rule.get('access_check_args', {})
                        
                        # Call the function with the appropriate arguments
                        if hasattr(check_func, '__code__') and check_func.__code__.co_argcount == 3:
                            # Function expects (user, app_name, required_level)
                            app_name_arg = access_check_args.get('app_name', app_name)
                            required_level = access_check_args.get('required_level', 'view')
                            if not check_func(request.user, app_name_arg, required_level):
                                logger.warning(f"User {request.user.username} failed custom access check for {app_name_arg}:{url_name}")
                                
                                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                    return JsonResponse({
                                        'success': False,
                                        'error': 'Access denied by custom check',
                                        'redirect': reverse('core:dashboard')
                                    }, status=403)
                                
                                messages.warning(request, rule.get('access_denied_message', 'You do not have access to this area.'))
                                return redirect(rule.get('failure_url', 'core:dashboard'))
                        else:
                            # Fallback for other function signatures
                            if not check_func(request, *view_args, **view_kwargs):
                                logger.warning(f"User {request.user.username} failed custom access check for {app_name}:{url_name}")
                                
                                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                    return JsonResponse({
                                        'success': False,
                                        'error': 'Access denied by custom check',
                                        'redirect': reverse('core:dashboard')
                                    }, status=403)
                                
                                messages.warning(request, rule.get('access_denied_message', 'You do not have access to this area.'))
                                return redirect(rule.get('failure_url', 'core:dashboard'))
                                
                    except (ImportError, AttributeError) as e:
                        logger.error(f"Error loading access check function {access_check}: {str(e)}")
                        raise ImproperlyConfigured(f"Could not load access check function: {access_check}")
        
        except Exception as e:
            logger.exception(f"Error in EmployeeAccessMiddleware: {str(e)}")
            return None
        
        # Continue processing the request
        return None
    
    def _is_auth_view(self, app_name, url_name):
        """Check if current view is an authentication view that should be skipped"""
        auth_views = getattr(settings, 'AUTH_VIEWS', [
            ('core', 'login'), ('shop', 'login'), ('blog', 'login'), 
            ('website', 'login'), ('core', 'logout'), ('core', 'register')
        ])
        return (app_name, url_name) in auth_views
    
    def _is_public_quote_view(self, app_name, url_name, view_kwargs):
        """Check if this is a public quote view that doesn't require authentication"""
        if app_name == 'quotes':
            public_quote_views = [
                'quote_preview_public',
                'quote_accept_public', 
                'quote_feedback_public',
                'quote_download_public',
                'quote_contact_public'
            ]
            return url_name in public_quote_views
        return False
    
    def _check_quote_specific_access(self, request, url_name, view_kwargs):
        """Handle quote-specific access control logic"""
        try:
            # Check if user is trying to access a specific quote
            quote_id = view_kwargs.get('quote_id') or view_kwargs.get('pk')
            
            if quote_id and not request.user.profile.is_admin:
                from quotes.models import Quote
                
                try:
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
                    
                    # Check if quote operations are allowed based on status
                    if url_name in ['quote_builder', 'quote_edit', 'add_quote_item', 'update_quote_item']:
                        if quote.status in ['accepted', 'converted', 'cancelled']:
                            error_msg = f'Quote cannot be edited in {quote.get_status_display()} status'
                            
                            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                                return JsonResponse({
                                    'success': False,
                                    'error': error_msg
                                }, status=400)
                            
                            messages.warning(request, error_msg)
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
            logger.error(f"Error in quote-specific access check: {str(e)}")
            return None
        
        return None
    
    def _get_access_rule(self, app_name, url_name):
        """Get access rule for the specified view"""
        # Try exact match
        rule_key = f"{app_name}:{url_name}"
        if rule_key in self.access_rules:
            return self.access_rules[rule_key]
        
        # Try pattern match for prefixes
        for pattern, rule in self.access_rules.items():
            if ':' in pattern:
                pattern_app, pattern_url = pattern.split(':')
                if pattern_app == app_name and pattern_url.endswith('*'):
                    prefix = pattern_url[:-1]  # Remove the asterisk
                    if url_name.startswith(prefix):
                        return rule
        
        return None

class QuoteWorkflowMiddleware:
    """
    Specialized middleware for quote workflow management and automation.
    
    This middleware handles quote-specific business logic such as automatic
    status transitions, expiration checks, and follow-up scheduling.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Process quote-related automation after response
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            if request.user.profile.can_manage_quotes:
                self._process_quote_automation(request)
        
        return response
    
    def _process_quote_automation(self, request):
        """Process automated quote workflow tasks"""
        try:
            from quotes.models import Quote
            from .utils import create_notification
            
            # Check for quotes that need follow-up (run this check only occasionally)
            import random
            if random.randint(1, 100) <= 5:  # 5% chance to run on each request
                self._check_overdue_followups(request.user)
                self._check_expiring_quotes(request.user)
                
        except Exception as e:
            logger.error(f"Error in quote workflow automation: {str(e)}")
    
    def _check_overdue_followups(self, user):
        """Check for quotes that need follow-up attention"""
        try:
            from quotes.models import Quote
            from django.db.models import Q
            
            # Find quotes that need follow-up
            overdue_quotes = Quote.objects.filter(
                Q(assigned_to=user) | Q(created_by=user),
                status__in=['sent', 'viewed', 'under_review'],
                sent_date__lte=timezone.now() - timezone.timedelta(days=7)
            )
            
            if overdue_quotes.exists() and not hasattr(user, '_followup_notification_sent'):
                # Prevent multiple notifications in same session
                user._followup_notification_sent = True
                
                quote_numbers = [q.quote_number for q in overdue_quotes[:3]]
                quote_list = ', '.join(quote_numbers)
                if overdue_quotes.count() > 3:
                    quote_list += f' and {overdue_quotes.count() - 3} more'
                
                from .utils import create_notification
                create_notification(
                    user=user,
                    title="Quotes Need Follow-up",
                    message=f"You have {overdue_quotes.count()} quotes that may need follow-up: {quote_list}",
                    notification_type="warning",
                    action_url=reverse('quotes:quote_list') + '?status=sent,viewed,under_review',
                    action_text="Review Quotes"
                )
                
        except Exception as e:
            logger.error(f"Error checking overdue followups: {str(e)}")
    
    def _check_expiring_quotes(self, user):
        """Check for quotes that are expiring soon"""
        try:
            from quotes.models import Quote
            from django.db.models import Q
            
            # Find quotes expiring in next 3 days
            expiring_quotes = Quote.objects.filter(
                Q(assigned_to=user) | Q(created_by=user),
                status__in=['sent', 'viewed', 'under_review'],
                validity_date__lte=timezone.now().date() + timezone.timedelta(days=3),
                validity_date__gt=timezone.now().date()
            )
            
            if expiring_quotes.exists() and not hasattr(user, '_expiring_notification_sent'):
                # Prevent multiple notifications in same session
                user._expiring_notification_sent = True
                
                from .utils import create_notification
                create_notification(
                    user=user,
                    title="Quotes Expiring Soon",
                    message=f"You have {expiring_quotes.count()} quotes expiring in the next 3 days",
                    notification_type="warning",
                    action_url=reverse('quotes:quote_list') + '?expiring_soon=true',
                    action_text="Review Expiring Quotes"
                )
                
        except Exception as e:
            logger.error(f"Error checking expiring quotes: {str(e)}")

class LoginRateLimitMiddleware:
    """
    Enhanced rate limiting middleware with quote system awareness.
    
    This middleware provides intelligent rate limiting that can be more
    lenient for sales team members who might be accessing the system
    frequently for client interactions.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Only apply to login views
        try:
            resolver_match = resolve(request.path_info)
            if resolver_match.url_name == 'login' and request.method == 'POST':
                from django.core.cache import cache
                from django.http import HttpResponseForbidden
                
                # Get client IP
                ip_address = self._get_client_ip(request)
                cache_key = f"login_attempts:{ip_address}"
                
                # Get attempt count from cache
                attempts = cache.get(cache_key, 0)
                
                # Dynamic rate limiting based on context
                max_attempts = self._get_max_attempts(request)
                block_time = getattr(settings, 'LOGIN_BLOCK_TIME', 300)  # 5 minutes default
                
                if attempts >= max_attempts:
                    logger.warning(f"Login rate limit exceeded for IP: {ip_address}")
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'error': f'Too many login attempts. Please try again in {block_time // 60} minutes.',
                            'retry_after': block_time
                        }, status=429)
                    
                    messages.error(request, f"Too many login attempts. Please try again in {block_time // 60} minutes.")
                    return HttpResponseForbidden("Too many login attempts")
                
                # Increment attempt count
                cache.set(cache_key, attempts + 1, block_time)
                
        except Exception as e:
            logger.exception(f"Error in LoginRateLimitMiddleware: {str(e)}")
        
        return None
    
    def _get_max_attempts(self, request):
        """Get maximum attempts based on context"""
        # Default limit
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
        
        # Check if this might be a sales team member based on user agent or other hints
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if 'mobile' in user_agent:
            # Be more lenient for mobile users (sales reps in the field)
            max_attempts += 2
        
        return max_attempts
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class PerformanceMonitoringMiddleware:
    """
    Performance monitoring middleware for quote system optimization.
    
    This middleware tracks performance metrics for quote-related operations
    to help identify bottlenecks and optimization opportunities.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        import time
        start_time = time.time()
        
        # Add start time to request for use in context processors
        request._start_time = start_time
        
        response = self.get_response(request)
        
        # Log slow quote operations
        if hasattr(request, 'resolver_match') and request.resolver_match:
            if request.resolver_match.namespace == 'quotes':
                processing_time = time.time() - start_time
                
                if processing_time > 2.0:  # Log operations taking more than 2 seconds
                    logger.warning(
                        f"Slow quote operation: {request.resolver_match.url_name} "
                        f"took {processing_time:.2f}s for user {getattr(request.user, 'username', 'anonymous')}"
                    )
        
        return response
