"""
Enhanced utility functions for the core app core/utils.py
"""
import os
import uuid
import logging
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.urls import reverse
from decimal import Decimal
from .models import Notification, SecurityEvent, AuditLog, ApprovalRequest
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger('core.authentication')

def create_notification(user, title, message, notification_type='info', action_url=None, action_text=None):
    """
    Enhanced notification creation with quote system support.        
    Example:
        create_notification(
            user=sales_rep,
            title="Quote Requires Follow-up",
            message="Quote #QUO-2024-0123 has been viewed by client",
            notification_type="quote",
            action_url="/quotes/123/",
            action_text="View Quote"
        )
    """
    try:
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            type=notification_type,
            action_url=action_url,
            action_text=action_text or ""
        )
        
        # Update notification cache with the new count
        cache_key = f"user_notifications:{user.id}"
        cached_count = cache.get(cache_key, 0)
        cache.set(cache_key, cached_count + 1, 3600)  # Cache for 1 hour
        
        # Log quote-specific notifications for audit trail
        if notification_type == 'quote':
            logger.info(f"Quote notification created for user {user.username}: {title}")
        
        return notification
    except Exception as e:
        logger.error(f"Error creating notification for user {user.username}: {str(e)}")
        return None

def create_bulk_notifications(users, title, message, notification_type='info', action_url=None, action_text=None):
    """
    Enhanced bulk notification creation with quote system support.
    
    This is particularly useful for notifying sales teams about quote-related
    events, policy changes, or system updates that affect quote management.
    
    Args:
        users: Queryset or list of User objects
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        action_url: Optional URL for notification action (NEW)
        action_text: Optional text for action button (NEW)
        
    Returns:
        List of created Notification objects
    """
    try:
        # Use bulk_create for better performance
        with transaction.atomic():
            notifications = []
            for user in users:
                notification = Notification(
                    user=user,
                    title=title,
                    message=message,
                    type=notification_type,
                    action_url=action_url,
                    action_text=action_text
                )
                notifications.append(notification)
            
            created_notifications = Notification.objects.bulk_create(notifications)
            
            # Update notification caches for all users
            for user in users:
                cache_key = f"user_notifications:{user.id}"
                cached_count = cache.get(cache_key, 0)
                cache.set(cache_key, cached_count + 1, 3600)
            
            logger.info(f"Bulk notifications created for {len(users)} users: {title}")
            return created_notifications
    except Exception as e:
        logger.error(f"Error creating bulk notifications: {str(e)}")
        return []

def create_quote_notification(user, title, message, quote_id=None, notification_type="quote"):
    """
    Specialized function for creating quote-specific notifications.
    
    This function automatically generates appropriate action URLs for quote
    notifications, making it easy to create interactive notifications that
    guide users directly to relevant quote actions.
    
    Args:
        user: User to notify
        title: Notification title
        message: Notification message
        quote_id: ID of the related quote (optional)
        notification_type: Type of notification (defaults to 'quote')
        
    Returns:
        Notification object
    """
    action_url = None
    action_text = None
    
    if quote_id:
        action_url = reverse('quotes:quote_detail', args=[quote_id])
        action_text = 'View Quote'
    
    return create_notification(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url,
        action_text=action_text
    )

def check_app_permission(user, app_name, required_level='view'):
    """
    Enhanced permission checking with quote system support.
    
    This function maintains your existing permission architecture while adding
    intelligent defaults for quote-related permissions based on user roles.
    
    Args:
        user: User object
        app_name: Name of the app ('quotes', 'crm', 'inventory', etc.)
        required_level: Minimum permission level ('view', 'edit', 'admin')
        
    Returns:
        Boolean indicating if user has permission
    """
    # Permission level hierarchy for consistent evaluation
    permission_levels = {
        'view': 0,
        'edit': 1,
        'admin': 2
    }
    
    # Cache key for permission checks
    cache_key = f"user_permissions:{user.id}:{app_name}"
    cached_level = cache.get(cache_key)
    
    if cached_level is not None:
        # Return result from cache
        user_level = permission_levels.get(cached_level, -1)
        required_level_value = permission_levels.get(required_level, 0)
        return user_level >= required_level_value
    
    # Super users always have access to everything
    if user.is_superuser:
        cache.set(cache_key, 'admin', 3600)
        return True
    
    # Check if user has profile (required for role-based permissions)
    if not hasattr(user, 'profile'):
        cache.set(cache_key, '', 3600)
        return False
    
    # Admins always have access to everything
    if user.profile.is_admin:
        cache.set(cache_key, 'admin', 3600)
        return True
    
    # Special handling for quote permissions based on user roles
    if app_name == 'quotes':
        # Sales managers get admin access to quotes
        if user.profile.user_type == 'sales_manager':
            cache.set(cache_key, 'admin', 3600)
            return True
        
        # Sales reps get edit access to quotes
        if user.profile.user_type == 'sales_rep':
            permission_level = 'edit'
            user_level = permission_levels.get(permission_level, -1)
            required_level_value = permission_levels.get(required_level, 0)
            cache.set(cache_key, permission_level, 3600)
            return user_level >= required_level_value
        
        # General employees get view access to quotes
        if user.profile.is_employee:
            permission_level = 'view'
            user_level = permission_levels.get(permission_level, -1)
            required_level_value = permission_levels.get(required_level, 0)
            cache.set(cache_key, permission_level, 3600)
            return user_level >= required_level_value
    
    # Check specific app permissions in database
    try:
        user_permission = user.app_permissions.get(app=app_name)
        user_level = permission_levels.get(user_permission.permission_level, -1)
        required_level_value = permission_levels.get(required_level, 0)
        
        # Cache the result
        cache.set(cache_key, user_permission.permission_level, 3600)
        
        return user_level >= required_level_value
    except Exception:
        # No specific permission found - cache negative result
        cache.set(cache_key, '', 3600)
        return False

def log_security_event(user=None, event_type=None, ip_address=None, user_agent=None, details=None):
    """Enhanced security event logging"""
    try:
        SecurityEvent.objects.create(
            user=user,
            event_type=event_type,
            ip_address=ip_address or 'unknown',
            user_agent=user_agent or '',
            details=details or {}
        )
        
        # Log critical events
        if event_type in ['login_failure', 'suspicious_activity', 'account_lockout']:
            logger.warning(f"Security event: {event_type} for user {user.username if user else 'unknown'} from IP {ip_address}")
        else:
            logger.info(f"Security event: {event_type} for user {user.username if user else 'unknown'}")
            
    except Exception as e:
        logger.error(f"Failed to log security event: {str(e)}")

def send_approval_notification_email(approval_request, action, reviewer):
    """Send email notification for approval actions"""
    try:
        user = approval_request.user
        subject = f"BlitzTech Electronics - Access Request {action.title()}"
        
        context = {
            'user': user,
            'approval_request': approval_request,
            'action': action,
            'reviewer': reviewer,
            'company_name': settings.COMPANY_NAME,
            'site_url': settings.SITE_URL,
        }
        
        # Render email templates
        text_content = render_to_string('core/emails/approval_notification.txt', context)
        html_content = render_to_string('core/emails/approval_notification.html', context)
        
        # Send email
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        send_mail(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
        
        logger.info(f"Approval notification sent to {user.email} for {action}")
        
    except Exception as e:
        logger.error(f"Failed to send approval notification: {str(e)}")

def send_welcome_email(user, user_type):
    """Send welcome email to new users"""
    try:
        subject = f"Welcome to {settings.COMPANY_NAME}!"
        
        context = {
            'user': user,
            'user_type': user_type,
            'company_name': settings.COMPANY_NAME,
            'site_url': settings.SITE_URL,
            'login_url': f"{settings.SITE_URL}{reverse('core:login')}",
            'profile_url': f"{settings.SITE_URL}{reverse('core:profile_completion')}",
        }
        
        # Render email templates
        text_content = render_to_string('core/emails/welcome_email.txt', context)
        html_content = render_to_string('core/emails/welcome_email.html', context)
        
        # Send email
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        send_mail(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
        
        logger.info(f"Welcome email sent to {user.email}")
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")

def notify_admins_new_user(user, user_type):
    """Notify admins about new user registrations"""
    try:
        # Get admin users
        admin_emails = getattr(settings, 'APPROVAL_NOTIFICATION_EMAILS', [])
        
        if not admin_emails:
            admin_users = User.objects.filter(
                is_superuser=True
            ).values_list('email', flat=True)
            admin_emails = list(admin_users)
        
        if admin_emails:
            subject = f"New User Registration - {settings.COMPANY_NAME}"
            
            context = {
                'user': user,
                'user_type': user_type,
                'company_name': settings.COMPANY_NAME,
                'admin_url': f"{settings.SITE_URL}{reverse('core:user_management')}",
                'approval_url': f"{settings.SITE_URL}{reverse('core:manage_approvals')}",
            }
            
            # Render email templates
            text_content = render_to_string('core/emails/admin_new_user.txt', context)
            html_content = render_to_string('core/emails/admin_new_user.html', context)
            
            # Send email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=admin_emails
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            send_mail(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
            
            logger.info(f"Admin notification sent for new user {user.username}")
            
    except Exception as e:
        logger.error(f"Failed to send admin notification: {str(e)}")

def check_user_access_level(user, required_access):
    """Check if user has required access level"""
    if not user.is_authenticated or not hasattr(user, 'profile'):
        return False
        
    profile = user.profile
    
    # Employee access is based on permissions
    if profile.user_type == 'employee':
        return check_app_permission(user, required_access, 'view')
    
    # Customer/blogger access based on approval status
    access_map = {
        'shop': profile.can_access_shop(),
        'crm': profile.can_access_crm(),
        'blog': profile.can_access_blog(),
    }
    
    return access_map.get(required_access, False)

def get_user_dashboard_stats(user):
    """Get dashboard statistics for user"""
    if not hasattr(user, 'profile'):
        return {}
    
    profile = user.profile
    stats = {
        'profile_completed': profile.profile_completed,
        'approval_requests': {
            'pending': user.approval_requests.filter(status='pending').count(),
            'approved': user.approval_requests.filter(status='approved').count(),
            'rejected': user.approval_requests.filter(status='rejected').count(),
        },
        'notifications': {
            'unread': user.notifications.filter(is_read=False).count(),
            'total': user.notifications.count(),
        },
        'access_status': {
            'shop': profile.can_access_shop(),
            'crm': profile.can_access_crm(),
            'blog': profile.can_access_blog() if profile.user_type == 'blogger' else False,
        }
    }
    
    return stats

def cleanup_old_security_events(days=90):
    """Clean up old security events (run as periodic task)"""
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        deleted_count = SecurityEvent.objects.filter(timestamp__lt=cutoff_date).delete()[0]
        logger.info(f"Cleaned up {deleted_count} old security events")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to cleanup security events: {str(e)}")
        return 0

def auto_approve_old_requests():
    """Auto-approve old requests based on business rules (run as periodic task)"""
    try:
        from django.conf import settings
        
        approval_settings = getattr(settings, 'APPROVAL_WORKFLOW', {})
        auto_approved = 0
        
        for user_type, config in approval_settings.items():
            auto_approve_hours = config.get('auto_approve_after_hours')
            if auto_approve_hours:
                cutoff_time = timezone.now() - timezone.timedelta(hours=auto_approve_hours)
                
                # Get old pending requests for this user type
                old_requests = ApprovalRequest.objects.filter(
                    user__profile__user_type=user_type,
                    status='pending',
                    requested_at__lt=cutoff_time
                )
                
                # Auto-approve them
                for request in old_requests:
                    request.approve(
                        reviewer=None,  # System approval
                        notes=f"Auto-approved after {auto_approve_hours} hours"
                    )
                    auto_approved += 1
        
        if auto_approved > 0:
            logger.info(f"Auto-approved {auto_approved} old requests")
        
        return auto_approved
        
    except Exception as e:
        logger.error(f"Failed to auto-approve requests: {str(e)}")
        return 0

def invalidate_permission_cache(user_id):
    """
    Enhanced cache invalidation that handles quote-specific permissions.
    
    When permissions change, this function ensures that all related caches
    are properly cleared, including quote-specific permission caches.
    """
    try:
        # Invalidate general permission cache
        pattern = f"user_permissions:{user_id}:*"
        
        # Get all cache keys matching the pattern
        # Note: This is a simplified version - in production you might use
        # a more sophisticated cache invalidation strategy
        for app in ['quotes', 'crm', 'inventory', 'financial', 'reports', 'admin']:
            cache_key = f"user_permissions:{user_id}:{app}"
            cache.delete(cache_key)
        
        # Also invalidate notification cache
        notification_cache_key = f"user_notifications:{user_id}"
        cache.delete(notification_cache_key)
        
        logger.debug(f"Permission cache invalidated for user {user_id}")
    except Exception as e:
        logger.error(f"Error invalidating permission cache for user {user_id}: {str(e)}")

def get_user_permissions_dict(user):
    """
    Get a comprehensive dictionary of user permissions for template use.
    
    This function provides a complete overview of what a user can access,
    which is particularly useful for building dynamic navigation menus
    and conditional feature access in templates.
    
    Args:
        user: User object
        
    Returns:
        Dictionary with app names as keys and permission levels as values
    """
    if not user.is_authenticated or not hasattr(user, 'profile'):
        return {}
    
    # Cache key for the complete permissions dictionary
    cache_key = f"user_permissions_dict:{user.id}"
    permissions_dict = cache.get(cache_key)
    
    if permissions_dict is not None:
        return permissions_dict
    
    # Build permissions dictionary
    permissions_dict = {}
    
    # Define all possible apps
    all_apps = ['crm', 'inventory', 'shop', 'website', 'blog', 'hr', 'admin', 'quotes', 'financial', 'reports']
    
    for app in all_apps:
        # Check permission level for each app
        if check_app_permission(user, app, 'admin'):
            permissions_dict[app] = 'admin'
        elif check_app_permission(user, app, 'edit'):
            permissions_dict[app] = 'edit'
        elif check_app_permission(user, app, 'view'):
            permissions_dict[app] = 'view'
        else:
            permissions_dict[app] = None
    
    # Cache the complete dictionary
    cache.set(cache_key, permissions_dict, 3600)
    return permissions_dict

def get_quote_dashboard_stats(user):
    """
    Get quote-specific dashboard statistics for a user.
    
    This function provides the key metrics that sales team members need
    to see on their dashboard, filtered appropriately based on their role
    and permissions.
    
    Args:
        user: User object
        
    Returns:
        Dictionary with quote statistics
    """
    if not check_app_permission(user, 'quotes', 'view'):
        return {}
    
    try:
        from quotes.models import Quote
        from django.db.models import Q, Count, Sum
        
        # Build user filter based on role
        if user.profile.is_admin:
            user_filter = Q()  # Admins see everything
        else:
            user_filter = Q(assigned_to=user) | Q(created_by=user)
        
        # Get base queryset
        quotes = Quote.objects.filter(user_filter)
        
        # Calculate key statistics
        total_quotes = quotes.count()
        active_quotes = quotes.filter(
            status__in=['draft', 'sent', 'viewed', 'under_review']
        ).count()
        
        # This month's metrics
        this_month = timezone.now().replace(day=1)
        month_quotes = quotes.filter(created_at__gte=this_month)
        month_value = month_quotes.filter(
            status__in=['accepted', 'converted']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Quotes needing attention
        needs_attention = quotes.filter(status='draft').count()
        
        # Expiring soon (next 7 days)
        expiring_soon = quotes.filter(
            status__in=['sent', 'viewed', 'under_review'],
            validity_date__lte=timezone.now().date() + timezone.timedelta(days=7)
        ).count()
        
        # Follow-up needed (sent more than 3 days ago with no response)
        followup_needed = quotes.filter(
            status__in=['sent', 'viewed'],
            sent_date__lte=timezone.now() - timezone.timedelta(days=3)
        ).count()
        
        return {
            'total_quotes': total_quotes,
            'active_quotes': active_quotes,
            'month_value': float(month_value),
            'needs_attention': needs_attention,
            'expiring_soon': expiring_soon,
            'followup_needed': followup_needed,
            'month_count': month_quotes.count(),
        }
        
    except Exception as e:
        logger.error(f"Error getting quote dashboard stats for user {user.username}: {str(e)}")
        return {}

def setup_default_user_permissions(user):
    """
    Set up default permissions for a new user based on their type.
    
    This function is called when a user's type changes or when setting up
    a new employee, ensuring they get appropriate default permissions for
    their role including quote access.
    
    Args:
        user: User object to set up permissions for
    """
    if not hasattr(user, 'profile'):
        return
    
    # Define default permission mappings
    permission_mappings = {
        'customer': {},  # Customers get no internal app access
        'blogger': {'blog': 'edit'},
        'employee': {
            'crm': 'view',
            'inventory': 'view',
            'quotes': 'view',
        },
        'sales_rep': {
            'crm': 'edit',
            'inventory': 'view',
            'quotes': 'edit',
            'financial': 'view',
            'reports': 'view',
        },
        'sales_manager': {
            'crm': 'admin',
            'inventory': 'view',
            'quotes': 'admin',
            'financial': 'edit',
            'reports': 'admin',
        },
        'blitzhub_admin': {
            'crm': 'admin',
            'inventory': 'admin',
            'shop': 'admin',
            'website': 'admin',
            'blog': 'admin',
            'quotes': 'admin',
            'financial': 'admin',
            'reports': 'admin',
        },
        'it_admin': {
            'crm': 'admin',
            'inventory': 'admin',
            'shop': 'admin',
            'website': 'admin',
            'blog': 'admin',
            'hr': 'admin',
            'admin': 'admin',
            'quotes': 'admin',
            'financial': 'view',
            'reports': 'admin',
        }
    }
    
    user_type = user.profile.user_type
    permissions = permission_mappings.get(user_type, {})
    
    try:
        with transaction.atomic():
            from .models import AppPermission
            
            for app, level in permissions.items():
                AppPermission.objects.update_or_create(
                    user=user,
                    app=app,
                    defaults={'permission_level': level}
                )
            
            # Invalidate permission cache for this user
            invalidate_permission_cache(user.id)
            
            logger.info(f"Default permissions set up for user {user.username} as {user_type}")
            
    except Exception as e:
        logger.error(f"Error setting up default permissions for user {user.username}: {str(e)}")

def generate_quote_number():
    """
    Generate a unique quote number using business-friendly format.
    
    This function creates quote numbers in the format QUO-YYYY-NNNN,
    which is easy for staff and clients to reference and track.
    
    Returns:
        String: Unique quote number
    """
    try:
        from quotes.models import Quote
        from django.db.models import Max
        
        current_year = timezone.now().year
        year_prefix = f"QUO-{current_year}-"
        
        # Find the highest number for this year
        latest_quote = Quote.objects.filter(
            quote_number__startswith=year_prefix
        ).aggregate(
            max_number=Max('quote_number')
        )['max_number']
        
        if latest_quote:
            # Extract the number part and increment
            number_part = int(latest_quote.split('-')[-1])
            new_number = number_part + 1
        else:
            # First quote of the year
            new_number = 1
        
        return f"{year_prefix}{new_number:04d}"
        
    except Exception as e:
        logger.error(f"Error generating quote number: {str(e)}")
        # Fallback to UUID-based number if database method fails
        import uuid
        return f"QUO-{timezone.now().year}-{str(uuid.uuid4())[:8].upper()}"

def get_navigation_context(user):
    """
    Get navigation context including quote system links.
    
    This function provides all the information needed to build dynamic
    navigation menus that show only the apps and features a user has
    access to, including new quote management sections.
    
    Args:
        user: User object
        
    Returns:
        Dictionary with navigation context
    """
    if not user.is_authenticated:
        return {}
    
    permissions = get_user_permissions_dict(user)
    
    # Build navigation sections
    navigation = {
        'main_apps': [],
        'management_apps': [],
        'admin_apps': [],
        'quote_stats': {},
    }
    
    # Main business applications
    if permissions.get('crm'):
        navigation['main_apps'].append({
            'name': 'CRM',
            'url': 'crm:dashboard',
            'icon': 'people',
            'permission': permissions['crm']
        })
    
    if permissions.get('quotes'):
        quote_stats = get_quote_dashboard_stats(user)
        navigation['main_apps'].append({
            'name': 'Quotes',
            'url': 'quotes:dashboard',
            'icon': 'file-earmark-text',
            'permission': permissions['quotes'],
            'badge': quote_stats.get('needs_attention', 0)
        })
        navigation['quote_stats'] = quote_stats
    
    if permissions.get('inventory'):
        navigation['main_apps'].append({
            'name': 'Inventory',
            'url': 'inventory:dashboard',
            'icon': 'boxes',
            'permission': permissions['inventory']
        })
    
    # Management applications
    if permissions.get('reports'):
        navigation['management_apps'].append({
            'name': 'Reports',
            'url': 'reports:dashboard',
            'icon': 'graph-up',
            'permission': permissions['reports']
        })
    
    if permissions.get('financial'):
        navigation['management_apps'].append({
            'name': 'Financial',
            'url': 'financial:dashboard',
            'icon': 'currency-dollar',
            'permission': permissions['financial']
        })
    
    # Admin applications
    if permissions.get('admin'):
        navigation['admin_apps'].append({
            'name': 'Administration',
            'url': 'admin:index',
            'icon': 'gear',
            'permission': permissions['admin']
        })
    
    return navigation

def get_profile_image_path(instance, filename):
    """
    Generate a unique filename for profile images
    
    Args:
        instance: UserProfile instance
        filename: Original filename
        
    Returns:
        Path string for the uploaded file
    """
    # Get file extension
    ext = filename.split('.')[-1]
    
    # Generate a unique filename
    unique_id = uuid.uuid4().hex
    new_filename = f"{instance.user.username}_{unique_id}.{ext}"
    
    return os.path.join('profile_images', new_filename)

def resize_profile_image(image_field, max_width=300, max_height=300, quality=85):
    """
    Resize a profile image to the specified dimensions
    
    Args:
        image_field: ImageField instance
        max_width: Maximum width for the resized image
        max_height: Maximum height for the resized image
        quality: JPEG compression quality (0-100)
        
    Returns:
        The resized image as a ContentFile
    """
    try:
        img = Image.open(image_field)
        
        # Preserve aspect ratio
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), Image.LANCZOS)
        
        # Convert to RGB if RGBA (remove alpha channel)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Save the image to a BytesIO object
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        # Get the filename and extension
        filename = os.path.basename(image_field.name)
        name, ext = os.path.splitext(filename)
        
        # Create a ContentFile with the new image
        return ContentFile(output.getvalue(), name=f"{name}_resized.jpg")
    except Exception as e:
        logger.error(f"Error resizing image {image_field.name}: {str(e)}")
        return None

def authenticate_user(request, username, password, remember_me=False):
    """
    Centralized authentication service with enhanced security
    """
    from django.contrib.auth import authenticate, login
    from .models import LoginActivity
    from django.core.cache import cache

    # Rate limiting check
    ip_address = get_client_ip(request)
    cache_key = f"login_attempts:{ip_address}"
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    cache_key = f"login_attempts:{ip_address}"
    attempts = cache.get(cache_key, 0)
    
    max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
    block_time = getattr(settings, 'LOGIN_BLOCK_TIME', 900)  # 15 minutes default
    
    if attempts >= max_attempts:
        log_security_event(
            user=None,
            event_type='login_failure',
            ip_address=ip_address,
            user_agent=user_agent,
            details={'reason': 'rate_limited', 'attempts': attempts}
        )
        return None
    
    # Authenticate user
    user = authenticate(username=username, password=password)
    
    if user is not None:
        # Check for suspicious activity
        if is_suspicious_activity(user, ip_address, user_agent):
            log_security_event(
                user=user,
                event_type='suspicious_activity',
                ip_address=ip_address,
                user_agent=user_agent,
                details={'reason': 'new_location_or_device'}
            )
            
            # Optionally send security alert email
            send_security_alert_email(user, ip_address, user_agent)
            
        # Reset login attempts on successful login
        cache.delete(cache_key)
        
        # Set session expiry based on remember_me
        if not remember_me:
            request.session.set_expiry(0)
            
        # Log the user in
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Log successful login
        log_security_event(
            user=user,
            event_type='login_success',
            ip_address=ip_address,
            user_agent=user_agent,
            details={'social_login': False}
        )
        
        # Update last login in profile
        if hasattr(user, 'profile'):
            user.profile.last_login = timezone.now()
            user.profile.save(update_fields=['last_login'])
        
        logger.info(f"Successful login for {username} from {ip_address}")
        return user
    else:
        # Increment failed login attempts
        cache.set(cache_key, attempts + 1, block_time)
        
        # Log failed login
        log_security_event(
            user=None,
            event_type='login_failure',
            ip_address=ip_address,
            user_agent=user_agent,
            details={'username': username, 'attempts': attempts + 1}
        )
        
        logger.warning(f"Failed login attempt for {username} from {ip_address}")
        return None

def get_client_ip(request):
    """
    Get the client's IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def is_suspicious_activity(user, ip_address, user_agent):
    """Detect suspicious login activity"""
    if not user or not hasattr(user, 'login_activities'):
        return False
    
    # Check for login from new location
    recent_ips = user.login_activities.filter(
        login_datetime__gte=timezone.now() - timezone.timedelta(days=30)
    ).values_list('ip_address', flat=True).distinct()
    
    if ip_address not in recent_ips and len(recent_ips) > 0:
        return True
    
    # Check for unusual user agent
    recent_agents = user.login_activities.filter(
        login_datetime__gte=timezone.now() - timezone.timedelta(days=7)
    ).values_list('user_agent', flat=True).distinct()
    
    if user_agent not in recent_agents and len(recent_agents) > 0:
        return True
    
    return False

def get_unread_notifications_count(user):
    """
    Get count of unread notifications with caching
    """
    cache_key = f"user_notifications:{user.id}"
    count = cache.get(cache_key)
    
    if count is None:
        # Cache miss, query the database
        count = Notification.objects.filter(user=user, is_read=False).count()
        cache.set(cache_key, count, 3600)  # Cache for 1 hour
    
    return count

def is_password_expired(user):
    """
    Check if a user's password has expired
    """
    password_expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', None)
    
    if not password_expiry_days:
        return False
        
    # Use last_password_change from profile, or fallback to date_joined
    last_change = getattr(user, 'last_password_change', user.date_joined)
    days_since_change = (timezone.now() - last_change).days
    
    return days_since_change >= password_expiry_days

def update_department_permissions(department, app_name, level):
    """
    Update permissions for all users in a department
    """
    from django.db import transaction
    from .models import UserProfile, AppPermission

    # Get all users in the specified department
    users = UserProfile.objects.filter(department=department).select_related('user')
    
    count = 0
    # Bulk update permissions
    with transaction.atomic():
        for profile in users:
            user = profile.user
            # Update or create the permission
            app_perm, created = AppPermission.objects.update_or_create(
                user=user,
                app=app_name,
                defaults={'permission_level': level}
            )
            count += 1
            
            # Invalidate cache for this user
            invalidate_permission_cache(user.id)
    
    logger.info(f"Updated {app_name} permissions to {level} for {count} users in {department} department")
    return count

def log_audit_event(user, action, description, request=None, object_type='', object_id='', extra_data=None):
    ip = None
    agent = None
    if request:
        ip = request.META.get('REMOTE_ADDR')
        agent = request.META.get('HTTP_USER_AGENT')
    AuditLog.objects.create(
        user=user if user and user.is_authenticated else None,
        action=action,
        description=description,
        object_type=object_type,
        object_id=str(object_id) if object_id else '',
        ip_address=ip,
        user_agent=agent,
        extra_data=extra_data,
    )

def send_security_alert_email(user, ip_address, user_agent):
    """Send security alert email for suspicious activity"""
    try:
        subject = f"{settings.COMPANY_NAME} - Security Alert"
        
        context = {
            'user': user,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': timezone.now(),
            'company_name': settings.COMPANY_NAME,
        }

        text_content = render_to_string('core/emails/security_alert.txt', context)
        html_content = render_to_string('core/emails/security_alert.html', context)

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        send_mail(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])

    except Exception as e:
        logger.error(f"Failed to send security alert: {str(e)}")

def validate_business_rules(user, action, **kwargs):
    """Validate business rules for various actions"""
    if not hasattr(user, 'profile'):
        return False, "User profile not found"
    
    profile = user.profile
    
    if action == 'crm_access':
        if profile.user_type == 'employee':
            return True, "Employee access granted"
        elif profile.crm_approved and profile.profile_completed:
            return True, "CRM access approved"
        else:
            return False, "CRM access requires approval and completed profile"
    
    elif action == 'shop_access':
        return profile.shop_approved, "Shop access status"
    
    elif action == 'blog_access':
        if profile.user_type != 'blogger':
            return False, "Only bloggers can access blog management"
        return profile.blog_approved and profile.profile_completed, "Blog access status"
    
    return True, "Action allowed"