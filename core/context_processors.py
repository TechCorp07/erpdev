# core/context_processors.py - ENHANCED with Quote System Integration

"""
Enhanced context processors for seamless quote system integration.

Context processors are like having helpful assistants that automatically gather
and organize information for every page in your application. They ensure that
templates have access to user permissions, quote statistics, and navigation
data without requiring every view to explicitly provide this information.
"""

from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

def auth_context(request):
    """
    Enhanced authentication context with comprehensive quote system support.
    
    This context processor provides essential user information and permissions
    to every template, making it easy to build dynamic interfaces that adapt
    to user roles and capabilities.
    """
    context = {
        'is_employee': False,
        'is_manager': False,
        'is_admin': False,
        'is_it_admin': False,
        'is_sales_rep': False,         # NEW
        'is_sales_manager': False,     # NEW
        'can_manage_quotes': False,    # NEW
        'can_approve_quotes': False,   # NEW
        'employee_notifications': [],
        'unread_notification_count': 0,
        'app_permissions': {},
        'quote_dashboard_stats': {},   # NEW
        'navigation_context': {},      # NEW
    }
    
    # Skip processing for anonymous users
    if not request.user.is_authenticated:
        return context
        
    # Get user ID for cache keys
    user_id = request.user.id
    
    # Add user profile information if authenticated
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        
        # Enhanced profile info including new sales roles
        context.update({
            'is_employee': profile.is_employee,
            'is_manager': profile.is_manager,
            'is_admin': profile.is_admin,
            'is_it_admin': profile.is_it_admin,
            'is_sales_rep': profile.user_type == 'sales_rep',
            'is_sales_manager': profile.user_type == 'sales_manager',
            'can_manage_quotes': profile.can_manage_quotes,
            'can_approve_quotes': profile.can_approve_quotes,
            'user_profile': profile,
        })
        
        # Add notifications if user is an employee
        if profile.is_employee:
            # Get unread notification count from cache
            cache_key = f"user_notifications:{user_id}"
            unread_count = cache.get(cache_key)
            
            if unread_count is None:
                # Cache miss - this should be rare since we update the cache elsewhere
                from .models import Notification
                
                # Only fetch count for the indicator, not all notifications
                unread_count = Notification.objects.filter(
                    user=request.user, 
                    is_read=False
                ).count()
                
                # Cache the count for future requests
                cache.set(cache_key, unread_count, 3600)  # Cache for 1 hour
            
            # For the navbar indicator, we need 5 notifications max
            if unread_count > 0:
                from .models import Notification
                
                # Fetch only the most recent 5 unread notifications for the navbar
                notifications = Notification.objects.filter(
                    user=request.user, 
                    is_read=False
                ).select_related().order_by('-created_at')[:5]
                
                context.update({
                    'employee_notifications': notifications,
                })
            
            context['unread_notification_count'] = unread_count
            
            # Add comprehensive app permissions (cached)
            perm_cache_key = f"user_permissions_dict:{user_id}"
            permissions_dict = cache.get(perm_cache_key)
            
            if permissions_dict is None:
                # Cache miss for permissions dictionary
                from .models import AppPermission
                from .utils import get_user_permissions_dict
                
                permissions_dict = get_user_permissions_dict(request.user)
                
                # Cache the permissions dictionary
                cache.set(perm_cache_key, permissions_dict, 3600)  # Cache for 1 hour
            
            context['app_permissions'] = permissions_dict
            
            # Add quote dashboard statistics for users with quote access
            if permissions_dict.get('quotes'):
                quote_stats_cache_key = f"quote_dashboard_stats:{user_id}"
                quote_stats = cache.get(quote_stats_cache_key)
                
                if quote_stats is None:
                    from .utils import get_quote_dashboard_stats
                    quote_stats = get_quote_dashboard_stats(request.user)
                    
                    # Cache quote stats for shorter time (quote data changes more frequently)
                    cache.set(quote_stats_cache_key, quote_stats, 1800)  # Cache for 30 minutes
                
                context['quote_dashboard_stats'] = quote_stats
            
            # Add navigation context for dynamic menu building
            nav_cache_key = f"navigation_context:{user_id}"
            navigation_context = cache.get(nav_cache_key)
            
            if navigation_context is None:
                from .utils import get_navigation_context
                navigation_context = get_navigation_context(request.user)
                
                # Cache navigation context
                cache.set(nav_cache_key, navigation_context, 3600)  # Cache for 1 hour
            
            context['navigation_context'] = navigation_context
    
    return context

def quote_context_processor(request):
    """
    Quote-specific context processor for enhanced quote system integration.
    
    This processor adds quote-specific information that's useful across templates,
    such as quick access to quote creation tools and quote-related notifications.
    """
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        # Only add quote context for users with quote access
        from .utils import check_app_permission
        
        if check_app_permission(request.user, 'quotes', 'view'):
            try:
                from quotes.models import Quote
                from django.db.models import Q
                
                # Build user filter based on role
                if request.user.profile.is_admin:
                    user_filter = Q()  # Admins see everything
                else:
                    user_filter = Q(assigned_to=request.user) | Q(created_by=request.user)
                
                # Quick quote statistics for template use
                context.update({
                    'user_quote_count': Quote.objects.filter(user_filter).count(),
                    'user_draft_quotes': Quote.objects.filter(
                        user_filter, status='draft'
                    ).count(),
                    'user_pending_quotes': Quote.objects.filter(
                        user_filter, status__in=['sent', 'viewed', 'under_review']
                    ).count(),
                    'quotes_needing_followup': Quote.objects.filter(
                        user_filter,
                        status__in=['sent', 'viewed'],
                        sent_date__lte=timezone.now() - timezone.timedelta(days=3)
                    ).count(),
                })
                
                # Quick access to recent clients for quote creation
                if check_app_permission(request.user, 'quotes', 'edit'):
                    from crm.models import Client
                    
                    recent_clients = Client.objects.filter(
                        status__in=['prospect', 'client']
                    ).order_by('-last_contacted', '-created_at')[:5]
                    
                    context['recent_clients_for_quotes'] = recent_clients
                    
            except ImportError:
                # Quote system or CRM not available
                pass
    
    return context

def system_context_processor(request):
    """
    System-wide context processor for application-level information.
    
    This processor provides system settings and configuration that templates
    might need, such as company information for headers and footers.
    """
    context = {}
    
    try:
        from .models import SystemSetting
        
        # Cache system settings to avoid database hits on every request
        settings_cache_key = "system_settings_context"
        cached_settings = cache.get(settings_cache_key)
        
        if cached_settings is None:
            # Get commonly used system settings
            company_settings = SystemSetting.objects.filter(
                category='company',
                is_active=True
            ).values_list('key', 'value')
            
            cached_settings = dict(company_settings)
            
            # Cache for longer since system settings change infrequently
            cache.set(settings_cache_key, cached_settings, 7200)  # Cache for 2 hours
        
        # Add company information to context with fallback defaults
        context.update({
            'company_name': cached_settings.get('COMPANY_NAME', 'BlitzTech Electronics'),
            'company_phone': cached_settings.get('COMPANY_PHONE', '+263 XX XXX XXXX'),
            'company_email': cached_settings.get('COMPANY_EMAIL', 'info@blitztech.co.zw'),
            'company_website': cached_settings.get('COMPANY_WEBSITE', 'www.blitztech.co.zw'),
            'company_address': cached_settings.get('COMPANY_ADDRESS', 'Harare, Zimbabwe'),
        })
        
    except Exception as e:
        logger.error(f"Error in system context processor: {str(e)}")
        # Provide fallback company information
        context.update({
            'company_name': 'BlitzTech Electronics',
            'company_phone': '+263 XX XXX XXXX',
            'company_email': 'info@blitztech.co.zw',
            'company_website': 'www.blitztech.co.zw',
            'company_address': 'Harare, Zimbabwe',
        })
    
    return context

def performance_context_processor(request):
    """
    Performance-related context processor for monitoring and optimization.
    
    This processor adds performance metrics that can be useful for debugging
    and monitoring application performance in templates.
    """
    context = {}
    
    # Only add performance context for staff users in debug mode
    if (hasattr(request.user, 'is_staff') and request.user.is_staff and 
        getattr(settings, 'DEBUG', False)):
        
        import time
        from django.db import connection
        
        context.update({
            'request_start_time': getattr(request, '_start_time', time.time()),
            'sql_query_count': len(connection.queries),
        })
    
    return context

def breadcrumb_context_processor(request):
    """
    Breadcrumb context processor for enhanced navigation.
    
    This processor automatically generates breadcrumb navigation based on
    the current URL, making it easier for users to understand their location
    in the application hierarchy.
    """
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.is_employee:
            breadcrumbs = []
            
            # Get URL name and namespace
            if hasattr(request, 'resolver_match') and request.resolver_match:
                url_name = request.resolver_match.url_name
                namespace = request.resolver_match.namespace
                
                # Build breadcrumbs based on current location
                if namespace == 'core':
                    breadcrumbs.append({'title': 'Dashboard', 'url': '/core/dashboard/'})
                    
                    if url_name == 'employee_list':
                        breadcrumbs.append({'title': 'Employee Management', 'url': None})
                    elif url_name == 'profile':
                        breadcrumbs.append({'title': 'My Profile', 'url': None})
                    elif url_name == 'notifications':
                        breadcrumbs.append({'title': 'Notifications', 'url': None})
                        
                elif namespace == 'quotes':
                    breadcrumbs.append({'title': 'Dashboard', 'url': '/core/dashboard/'})
                    breadcrumbs.append({'title': 'Quotes', 'url': '/quotes/'})
                    
                    if url_name == 'quote_list':
                        breadcrumbs.append({'title': 'All Quotes', 'url': None})
                    elif url_name == 'quote_create':
                        breadcrumbs.append({'title': 'Create Quote', 'url': None})
                    elif url_name == 'quote_detail':
                        breadcrumbs.append({'title': 'Quote Details', 'url': None})
                    elif url_name == 'quote_builder':
                        breadcrumbs.append({'title': 'Quote Builder', 'url': None})
                        
                elif namespace == 'crm':
                    breadcrumbs.append({'title': 'Dashboard', 'url': '/core/dashboard/'})
                    breadcrumbs.append({'title': 'CRM', 'url': '/crm/'})
                    
                # Add more namespace handling as needed
                
            context['breadcrumbs'] = breadcrumbs
    
    return context

def feature_flags_context_processor(request):
    """
    Feature flags context processor for controlled feature rollouts.
    
    This processor adds feature flags that can be used to conditionally
    show or hide features in templates, useful for A/B testing or gradual
    feature rollouts.
    """
    context = {}
    
    if request.user.is_authenticated:
        # Define feature flags based on user role or other criteria
        feature_flags = {
            'new_quote_builder': True,  # Always enabled for now
            'advanced_analytics': request.user.profile.is_admin if hasattr(request.user, 'profile') else False,
            'bulk_quote_operations': (
                hasattr(request.user, 'profile') and 
                request.user.profile.user_type in ['sales_manager', 'blitzhub_admin', 'it_admin']
            ),
            'client_portal_preview': True,
            'quote_templates': True,
            'mobile_quote_access': True,
        }
        
        context['feature_flags'] = feature_flags
    
    return context
