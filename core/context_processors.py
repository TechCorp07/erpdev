from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q, Count, Sum
import logging
from core.utils import (
    get_user_permissions, has_app_permission, can_user_manage_roles,
    is_employee, is_admin_user, is_manager_user
)

logger = logging.getLogger(__name__)

def auth_context(request):
    """
    Enhanced authentication context with proper permission integration.
    """
    context = {
        'is_employee': False,
        'is_manager': False,
        'is_admin': False,
        'app_permissions': {},
        'unread_notification_count': 0,
    }
    
    # Skip processing for anonymous users
    if not request.user.is_authenticated:
        return context
        
    user = request.user
    user_id = user.id
    
    # Use cache to avoid expensive permission calculations on every request
    cache_key = f"user_context:{user_id}"
    cached_context = cache.get(cache_key)
    
    if cached_context is None:
        # Calculate fresh context
        try:
            # Get user permissions using our utility function
            app_permissions = get_user_permissions(user)
            
            # Determine user capabilities
            is_employee_user = is_employee(user)
            is_manager_user_check = is_manager_user(user)
            is_admin_user_check = is_admin_user(user)
            can_manage_users = can_user_manage_roles(user)
            
            # Build context
            fresh_context = {
                'is_employee': is_employee_user,
                'is_manager': is_manager_user_check,
                'is_admin': is_admin_user_check,
                'can_manage_users': can_manage_users,
                'app_permissions': app_permissions,
                'user_role_display': _get_user_role_display(user),
            }
            
            # Add profile information if available
            if hasattr(user, 'profile'):
                profile = user.profile
                fresh_context.update({
                    'user_profile': profile,
                    'user_type': profile.user_type,
                    'department': profile.department,
                    'profile_completed': profile.profile_completed,
                })
            
            # Cache for 5 minutes to balance performance and freshness
            cache.set(cache_key, fresh_context, 300)
            cached_context = fresh_context
            
        except Exception as e:
            logger.error(f"Error building auth context for user {user_id}: {e}")
            # Return basic context on error
            cached_context = {
                'is_employee': False,
                'is_manager': False,
                'is_admin': user.is_superuser,
                'app_permissions': {},
            }
    
    # Add dynamic data that shouldn't be cached
    context.update(cached_context)
    
    # Add notification count (this changes frequently, so don't cache)
    if context.get('is_employee'):
        try:
            from core.models import Notification
            context['unread_notification_count'] = Notification.objects.filter(
                user=user, is_read=False
            ).count()
        except Exception as e:
            logger.error(f"Error getting notification count for user {user_id}: {e}")
            context['unread_notification_count'] = 0
    
    return context

def _get_user_role_display(user):
    """Helper function to get user-friendly role display"""
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

def dashboard_context(request):
    """
    Additional context for dashboard-specific data.
    Only loads when needed to avoid performance impact on all pages.
    """
    # Only load dashboard context for dashboard pages
    if not request.resolver_match or 'dashboard' not in request.resolver_match.url_name:
        return {}
    
    if not request.user.is_authenticated:
        return {}
    
    user = request.user
    context = {}
    
    # Add dashboard-specific data
    try:
        # Get pending items that need attention
        context.update({
            'pending_quotes_count': _get_pending_quotes_count(user),
            'recent_activity_count': _get_recent_activity_count(user),
        })
        
        # Add quick stats for managers/admins
        if is_manager_user(user) or is_admin_user(user):
            context.update({
                'quick_stats': _get_quick_stats(user),
            })
            
    except Exception as e:
        logger.error(f"Error building dashboard context for user {user.id}: {e}")
    
    return context

def _get_pending_quotes_count(user):
    """Get count of pending quotes for user"""
    try:
        if has_app_permission(user, 'quotes', 'view'):
            from quotes.models import Quote  # Adjust import as needed
            return Quote.objects.filter(status='pending').count()
    except Exception:
        pass
    return 0

def _get_recent_activity_count(user):
    """Get count of recent activity items"""
    try:
        # You can implement this based on your activity tracking
        return 0
    except Exception:
        pass
    return 0

def _get_quick_stats(user):
    """Get quick statistics for dashboard"""
    try:
        from django.contrib.auth.models import User
        
        stats = {}
        
        # Basic user stats (for managers/admins)
        if has_app_permission(user, 'admin', 'view'):
            stats.update({
                'total_users': User.objects.count(),
                'active_employees': User.objects.filter(
                    profile__user_type='employee',
                    is_active=True
                ).count(),
                'pending_approvals': User.objects.filter(
                    profile__is_approved=False
                ).count(),
            })
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting quick stats: {e}")
        return {}

def feature_flags(request):
    """
    Feature flags for gradual rollout of new features.
    """
    context = {}
    
    if request.user.is_authenticated:
        is_admin = is_admin_user(request.user)
        is_manager = is_manager_user(request.user)
        
        # Define feature flags based on user role
        feature_flags = {
            'new_quote_builder': True,
            'advanced_analytics': is_admin or is_manager,
            'bulk_operations': is_admin,
            'beta_features': is_admin,
        }
        
        context['feature_flags'] = feature_flags
    
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
