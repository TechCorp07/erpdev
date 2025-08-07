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
        'is_sales_rep': False,
        'is_sales_manager': False,
        'can_manage_quotes': False,
        'can_approve_quotes': False,
        'employee_notifications': [],
        'unread_notification_count': 0,
        'app_permissions': {},
        'quote_dashboard_stats': {},
        'navigation_context': {},
    }
    
    # Skip processing for anonymous users
    if not request.user.is_authenticated:
        return context
        
    # Get user ID for cache keys
    user_id = request.user.id
    
    # Add user profile information if authenticated
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
        
        # Determine user roles based on current UserProfile structure
        is_employee = profile.user_type == 'employee'
        is_blogger = profile.user_type == 'blogger'
        is_customer = profile.user_type == 'customer'
        
        # Determine if user is admin/manager based on Django's built-in fields or department
        is_admin = request.user.is_superuser or request.user.is_staff
        is_manager = (profile.department in ['admin', 'sales'] and is_employee) or is_admin
        is_it_admin = (profile.department == 'it' and is_employee) or is_admin
        is_sales_rep = profile.department == 'sales' and is_employee
        is_sales_manager = profile.department == 'sales' and is_employee and is_manager
        
        # Enhanced profile info 
        context.update({
            'is_employee': is_employee,
            'is_manager': is_manager,
            'is_admin': is_admin,
            'is_it_admin': is_it_admin,
            'is_sales_rep': is_sales_rep,
            'is_sales_manager': is_sales_manager,
            'can_manage_quotes': is_manager or is_admin,  # Based on role logic
            'can_approve_quotes': is_manager or is_admin,  # Based on role logic
            'user_profile': profile,
        })
        
        # Add notifications if user is an employee
        if is_employee:
            # Get unread notification count from cache
            cache_key = f"user_notifications:{user_id}"
            unread_count = cache.get(cache_key)
            
            if unread_count is None:
                try:
                    from .models import Notification
                    unread_count = Notification.objects.filter(
                        user=request.user, 
                        is_read=False
                    ).count()
                    cache.set(cache_key, unread_count, timeout=300)  # 5 minutes
                except:
                    unread_count = 0
            
            context['unread_notification_count'] = unread_count
            
            # Get app permissions using the utility function
            try:
                from .utils import get_user_permissions
                context['app_permissions'] = get_user_permissions(request.user)
            except Exception as e:
                logger.warning(f"Could not load user permissions: {e}")
                context['app_permissions'] = {}
    
    return context

def quote_context_processor(request):
    """
    Quote-specific context processor.
    
    This processor adds quote-specific information that's useful across templates,
    such as quick access to quote creation tools and quote-related notifications.
    """
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        # Only add quote context for users with quote access
        try:
            from .utils import has_app_permission
            
            if has_app_permission(request.user, 'quotes', 'view'):
                try:
                    from quotes.models import Quote
                    from django.db.models import Q
                    
                    # Build user filter based on role
                    if request.user.is_superuser or request.user.is_staff:
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
                        ).count() if hasattr(Quote, 'sent_date') else 0,
                    })
                    
                    # Quick access to recent clients for quote creation
                    if has_app_permission(request.user, 'quotes', 'edit'):
                        try:
                            from crm.models import Client
                            
                            recent_clients = Client.objects.filter(
                                status__in=['prospect', 'client']
                            ).order_by('-last_contacted', '-created_at')[:5]
                            
                            context['recent_clients_for_quotes'] = recent_clients
                        except:
                            pass
                            
                except ImportError:
                    # Quote system or CRM not available
                    pass
        except ImportError:
            # utils not available
            pass
    
    return context

def system_context_processor(request):
    """
    System-wide context processor for application-level information.
    """
    context = {
        'app_name': 'BlitzTech Electronics',
        'company_name': 'BlitzTech Electronics',
    }
    
    return context

def breadcrumb_context_processor(request):
    """
    Breadcrumb context processor for enhanced navigation.
    """
    context = {}
    
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        if request.user.profile.user_type == 'employee':
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
                        
                elif namespace == 'crm':
                    breadcrumbs.append({'title': 'Dashboard', 'url': '/core/dashboard/'})
                    breadcrumbs.append({'title': 'CRM', 'url': '/crm/'})
                    
            context['breadcrumbs'] = breadcrumbs
    
    return context

def feature_flags_context_processor(request):
    """
    Feature flags context processor for controlled feature rollouts.
    """
    context = {}
    
    if request.user.is_authenticated:
        is_admin = request.user.is_superuser or request.user.is_staff
        is_manager = False
        
        if hasattr(request.user, 'profile'):
            is_manager = (
                request.user.profile.department in ['admin', 'sales'] and 
                request.user.profile.user_type == 'employee'
            ) or is_admin
        
        # Define feature flags based on user role
        feature_flags = {
            'new_quote_builder': True,
            'advanced_analytics': is_admin,
            'bulk_quote_operations': is_manager or is_admin,
            'client_portal_preview': True,
            'quote_templates': True,
            'mobile_quote_access': True,
        }
        
        context['feature_flags'] = feature_flags
    
    return context
