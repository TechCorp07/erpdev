"""
Enhanced utility functions for the core app core/utils.py
"""
from datetime import timedelta
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
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import (
    Notification, SecurityEvent, AuditLog, ApprovalRequest,
    AppPermission, EmployeeRole, UserRole
)

logger = logging.getLogger('core.authentication')

# =====================================
# ROLE & PERMISSION UTILITIES
# =====================================

def get_user_roles(user):
    """Get all active roles for a user with caching"""
    if not user.is_authenticated or not hasattr(user, 'profile'):
        return []
    
    if not user.profile.is_employee:
        return []
    
    cache_key = f'user_roles:{user.id}'
    roles = cache.get(cache_key)
    
    if roles is None:
        from .models import UserRole, EmployeeRole
        roles = list(
            EmployeeRole.objects.filter(
                users__user=user,
                users__is_active=True
            ).values_list('name', flat=True)
        )
        cache.set(cache_key, roles, timeout=300)  # 5 minutes
    
    return roles

def get_user_permissions(user):
    """Get all app permissions for a user based on their roles"""
    if not user.is_authenticated:
        return {}
    
    cache_key = f'user_permissions:{user.id}'
    permissions = cache.get(cache_key)
    
    if permissions is None:
        from .models import AppPermission
        
        permissions = {}
        user_roles = get_user_roles(user)
        
        if user_roles:
            # Get permissions from all user's roles
            role_permissions = AppPermission.objects.filter(
                role__name__in=user_roles
            ).select_related('role')
            
            for perm in role_permissions:
                app = perm.app
                level = perm.permission_level
                
                # Use highest permission level if multiple roles grant access
                current_level = permissions.get(app)
                if not current_level or _permission_level_value(level) > _permission_level_value(current_level):
                    permissions[app] = level
        
        cache.set(cache_key, permissions, timeout=300)  # 5 minutes
    
    return permissions

def _permission_level_value(level):
    """Get numeric value for permission level comparison"""
    levels = {'view': 1, 'edit': 2, 'admin': 3}
    return levels.get(level, 0)

def has_app_permission(user, app_name, required_level='view'):
    """Check if user has specific app permission"""
    if not user.is_authenticated:
        return False
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    permissions = get_user_permissions(user)
    user_level = permissions.get(app_name)
    
    if not user_level:
        return False
    
    return _permission_level_value(user_level) >= _permission_level_value(required_level)

def has_role(user, role_name):
    """Check if user has specific role"""
    if not user.is_authenticated:
        return False
    
    user_roles = get_user_roles(user)
    return role_name in user_roles

def can_user_manage_roles(user):
    """Check if user can assign/manage roles"""
    if not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    from .models import EmployeeRole
    user_roles = get_user_roles(user)
    
    # Check if any of user's roles allow role management
    return EmployeeRole.objects.filter(
        name__in=user_roles,
        can_assign_roles=True
    ).exists()

def requires_gm_approval(user, action_type='sensitive'):
    """Check if user's actions require GM approval"""
    if not user.is_authenticated:
        return True  # Default to requiring approval
    
    from .models import EmployeeRole
    user_roles = get_user_roles(user)
    
    # Business owners don't need approval
    if 'business_owner' in user_roles:
        return False
    
    # Check if any role requires GM approval
    return EmployeeRole.objects.filter(
        name__in=user_roles,
        requires_gm_approval=True
    ).exists()

# =====================================
# USER TYPE UTILITIES
# =====================================

def is_employee(user):
    """Clean check for employee status"""
    return (user.is_authenticated and 
            hasattr(user, 'profile') and 
            user.profile.user_type == 'employee')

def is_blogger(user):
    """Clean check for blogger status"""
    return (user.is_authenticated and 
            hasattr(user, 'profile') and 
            user.profile.user_type == 'blogger')

def is_customer(user):
    """Clean check for customer status"""
    return (user.is_authenticated and 
            hasattr(user, 'profile') and 
            user.profile.user_type == 'customer')

def is_admin_user(user):
    """Check if user has admin privileges"""
    return (user.is_superuser or user.is_staff or
            (hasattr(user, 'profile') and 
             user.profile.department == 'admin' and 
             user.profile.user_type == 'employee'))

def is_manager_user(user):
    """Check if user has manager privileges"""
    return (user.is_superuser or user.is_staff or
            (hasattr(user, 'profile') and 
             user.profile.department in ['admin', 'sales'] and 
             user.profile.user_type == 'employee'))

def can_access_admin(user):
    """Check if user can access admin features"""
    return is_admin_user(user)

def can_access_employee_areas(user):
    """Check if user can access employee-only areas"""
    return is_employee(user)

# =====================================
# PERMISSION CACHING UTILITIES
# =====================================

def invalidate_user_cache(user_id):
    """Invalidate all cached data for a user"""
    cache_keys = [
        f'user_roles:{user_id}',
        f'user_permissions:{user_id}',
        f'user_notifications:{user_id}',
        f'user_dashboard_stats:{user_id}',
    ]
    
    cache.delete_many(cache_keys)
    logger.info(f"Invalidated cache for user {user_id}")

def invalidate_permission_cache(user_id):
    """Invalidate all permission-related cache entries for a user"""
    cache_keys = [
        f'user_roles:{user_id}',
        f'user_permissions:{user_id}',
        f'dashboard_data:{user_id}'
    ]
    
    for key in cache_keys:
        cache.delete(key)
    
    logger.info(f"Invalidated permission cache for user ID: {user_id}")

# =====================================
# ROLE ASSIGNMENT UTILITIES
# =====================================

def assign_role_to_user(user, role_name, assigned_by=None):
    """Safely assign a role to a user"""
    from .models import EmployeeRole, UserRole
    
    if not user.profile.is_employee:
        raise ValueError("Can only assign roles to employees")
    
    try:
        role = EmployeeRole.objects.get(name=role_name)
        user_role, created = UserRole.objects.get_or_create(
            user=user,
            role=role,
            defaults={
                'assigned_by': assigned_by,
                'is_active': True,
            }
        )
        
        if not created and not user_role.is_active:
            user_role.is_active = True
            user_role.assigned_by = assigned_by
            user_role.assigned_at = timezone.now()
            user_role.save()
        
        # Invalidate user's cached permissions
        invalidate_user_cache(user.id)
        
        # Log the role assignment
        log_security_event(
            user=user,
            event_type='role_assigned',
            description=f'Role {role.display_name} assigned to {user.get_full_name()}',
            additional_data={'role': role_name, 'assigned_by': assigned_by.username if assigned_by else None}
        )
        
        return user_role
        
    except EmployeeRole.DoesNotExist:
        raise ValueError(f"Role {role_name} does not exist")

def remove_role_from_user(user, role_name, removed_by=None):
    """Safely remove a role from a user"""
    from .models import UserRole
    
    try:
        user_role = UserRole.objects.get(user=user, role__name=role_name, is_active=True)
        user_role.is_active = False
        user_role.save()
        
        # Invalidate user's cached permissions
        invalidate_user_cache(user.id)
        
        # Log the role removal
        log_security_event(
            user=user,
            event_type='role_removed',
            description=f'Role {role_name} removed from {user.get_full_name()}',
            additional_data={'role': role_name, 'removed_by': removed_by.username if removed_by else None}
        )
        
        return True
        
    except UserRole.DoesNotExist:
        return False

def get_assignable_roles(user):
    """Get roles that a user can assign to others"""
    if not can_user_manage_roles(user):
        return []
    
    from .models import EmployeeRole
    
    # Business owners can assign any role
    if has_role(user, 'business_owner'):
        return EmployeeRole.objects.all()
    
    # System admins can assign most roles (but might have restrictions)
    if has_role(user, 'system_admin'):
        return EmployeeRole.objects.exclude(name='business_owner')
    
    return []

# =====================================
# SECURITY UTILITIES
# =====================================

def log_security_event(user=None, event_type='general', description='', ip_address=None, user_agent='', additional_data=None):
    """Log security events for audit trail"""
    from .models import SecurityLog
    
    SecurityLog.objects.create(
        user=user,
        event_type=event_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        additional_data=additional_data or {}
    )

def check_password_strength(password):
    """Check password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    return True, "Password meets requirements"

def is_account_locked(user):
    """Check if user account is currently locked"""
    if not hasattr(user, 'profile'):
        return False
    
    if not user.profile.account_locked_until:
        return False
    
    return timezone.now() < user.profile.account_locked_until

def lock_account(user, duration_minutes=30):
    """Lock user account for specified duration"""
    if hasattr(user, 'profile'):
        user.profile.account_locked_until = timezone.now() + timedelta(minutes=duration_minutes)
        user.profile.save(update_fields=['account_locked_until'])
        
        log_security_event(
            user=user,
            event_type='account_locked',
            description=f'Account locked for {duration_minutes} minutes due to security concerns'
        )

# =====================================
# NOTIFICATION UTILITIES
# =====================================

def create_notification(user, notification_type, title, message):
    """Create a notification for a user"""
    from .models import Notification
    
    notification = Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        message=message
    )
    
    # Invalidate notification cache
    cache.delete(f'user_notifications:{user.id}')
    
    return notification

def get_unread_notifications_count(user):
    """Get count of unread notifications with caching"""
    if not user.is_authenticated:
        return 0
    
    cache_key = f'user_notifications:{user.id}'
    count = cache.get(cache_key)
    
    if count is None:
        from .models import Notification
        count = Notification.objects.filter(user=user, is_read=False).count()
        cache.set(cache_key, count, timeout=300)  # 5 minutes
    
    return count

# =====================================
# DASHBOARD UTILITIES
# =====================================

def get_user_dashboard_context(user):
    """Get comprehensive dashboard context for a user"""
    if not user.is_authenticated:
        return {}
    
    context = {
        'user_type': user.profile.user_type if hasattr(user, 'profile') else 'customer',
        'user_roles': get_user_roles(user),
        'app_permissions': get_user_permissions(user),
        'unread_notifications': get_unread_notifications_count(user),
        'can_manage_roles': can_user_manage_roles(user),
        'requires_gm_approval': requires_gm_approval(user),
    }
    
    # Add employee-specific context
    if is_employee(user):
        context.update({
            'department': user.profile.department,
            'can_access_admin': can_access_admin(user),
        })
    
    return context

def get_navigation_context(user):
    """Get navigation context for dashboard"""
    if not user.is_authenticated:
        return {}
    
    permissions = get_user_permissions(user)
    
    nav_items = []
    
    # Add navigation items based on permissions
    if permissions.get('crm'):
        nav_items.append({
            'name': 'CRM',
            'url': 'crm:dashboard',
            'icon': 'users',
            'permission_level': permissions['crm']
        })
    
    if permissions.get('quotes'):
        nav_items.append({
            'name': 'Quotes',
            'url': 'quotes:dashboard', 
            'icon': 'file-text',
            'permission_level': permissions['quotes']
        })
    
    if permissions.get('inventory'):
        nav_items.append({
            'name': 'Inventory',
            'url': 'inventory:dashboard',
            'icon': 'package',
            'permission_level': permissions['inventory']
        })
    
    if permissions.get('shop'):
        nav_items.append({
            'name': 'Shop Management',
            'url': 'shop:admin_dashboard',
            'icon': 'shopping-cart',
            'permission_level': permissions['shop']
        })
    
    if permissions.get('reports'):
        nav_items.append({
            'name': 'Reports',
            'url': 'core:system_reports',
            'icon': 'bar-chart',
            'permission_level': permissions['reports']
        })
    
    if permissions.get('admin') or user.is_superuser:
        nav_items.append({
            'name': 'Admin Panel',
            'url': 'core:system_settings',
            'icon': 'settings',
            'permission_level': 'admin'
        })
    
    return {
        'navigation_items': nav_items,
        'has_admin_access': bool(permissions.get('admin')) or user.is_superuser,
        'has_management_access': any(
            permissions.get(app) in ['edit', 'admin'] 
            for app in ['crm', 'quotes', 'inventory', 'hr']
        )
    }

# =====================================
# INITIALIZATION UTILITIES
# =====================================

def setup_default_permissions():
    """Setup default permissions for roles"""
    from .models import EmployeeRole, AppPermission
    
    # Default permission mappings
    role_permissions = {
        'business_owner': {
            'crm': 'admin', 'inventory': 'admin', 'shop': 'admin',
            'website': 'admin', 'blog': 'admin', 'hr': 'admin',
            'admin': 'admin', 'quotes': 'admin', 'financial': 'admin',
            'reports': 'admin'
        },
        'system_admin': {
            'crm': 'admin', 'inventory': 'admin', 'shop': 'admin',
            'website': 'admin', 'hr': 'admin', 'admin': 'admin',
            'quotes': 'admin', 'financial': 'view', 'reports': 'admin'
        },
        'sales_manager': {
            'crm': 'admin', 'quotes': 'admin', 'reports': 'view',
            'website': 'edit', 'shop': 'view'
        },
        'procurement_officer': {
            'inventory': 'admin', 'crm': 'view', 'reports': 'view'
        },
        'service_tech': {
            'inventory': 'admin', 'crm': 'edit', 'reports': 'view'
        },
        'accounting': {
            'financial': 'admin', 'reports': 'admin', 'crm': 'view',
            'inventory': 'view', 'quotes': 'view'
        }
    }
    
    for role_name, permissions in role_permissions.items():
        try:
            role = EmployeeRole.objects.get(name=role_name)
            for app, level in permissions.items():
                AppPermission.objects.get_or_create(
                    role=role,
                    app=app,
                    defaults={'permission_level': level}
                )
        except EmployeeRole.DoesNotExist:
            logger.warning(f"Role {role_name} not found, skipping permission setup")
    
    logger.info("Default permissions setup completed")

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

def get_recent_notifications(user, limit=5):
    """Get recent notifications for a user"""
    if not user.is_authenticated:
        return []
    
    from .models import Notification
    return Notification.objects.filter(
        user=user
    ).order_by('-created_at')[:limit]

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
            'company_name': getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics'),
            'site_url': getattr(settings, 'SITE_URL', 'https://blitztechelectronics.co.zw'),
        }
        
        # Render email templates
        text_content = render_to_string('core/emails/approval_notification.txt', context)
        html_content = render_to_string('core/emails/approval_notification.html', context)
        
        # Send email using EmailMultiAlternatives
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@blitztechelectronics.co.zw'),
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        # Also call send_mail for compatibility
        send_mail(
            subject, 
            text_content, 
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@blitztechelectronics.co.zw'), 
            [user.email]
        )
        
        logger.info(f"Approval notification sent to {user.email} for {action}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send approval notification: {str(e)}")
        return False

def send_welcome_email(user, user_type):
    """Send welcome email to new users"""
    try:
        subject = f"Welcome to {getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics')}!"
        
        context = {
            'user': user,
            'user_type': user_type,
            'company_name': getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics'),
            'site_url': getattr(settings, 'SITE_URL', 'https://blitztechelectronics.co.zw'),
            'login_url': f"{getattr(settings, 'SITE_URL', 'https://blitztechelectronics.co.zw')}{reverse('core:login')}",
            'profile_url': f"{getattr(settings, 'SITE_URL', 'https://blitztechelectronics.co.zw')}{reverse('core:profile_completion')}",
        }
        
        # Render email templates  
        text_content = render_to_string('core/emails/welcome_email.txt', context)
        html_content = render_to_string('core/emails/welcome_email.html', context)
        
        # Send email
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@blitztechelectronics.co.zw'),
            to=[user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        
        # Also call send_mail for compatibility
        send_mail(
            subject, 
            text_content, 
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@blitztechelectronics.co.zw'), 
            [user.email]
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return False

def send_notification_email(user, title, message, email_type='notification'):
    """Generic function to send notification emails - for test compatibility"""
    try:
        subject = f"BlitzTech Electronics - {title}"
        
        context = {
            'user': user,
            'title': title,
            'message': message,
            'company_name': getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics'),
            'site_url': getattr(settings, 'SITE_URL', 'https://blitztechelectronics.co.zw'),
        }
        
        # Use a simple text template
        text_content = f"""
Hello {user.get_full_name() or user.username},

{message}

Best regards,
{getattr(settings, 'COMPANY_NAME', 'BlitzTech Electronics')} Team
"""
        
        # Send email
        send_mail(
            subject,
            text_content,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@blitztechelectronics.co.zw'),
            [user.email]
        )
        
        logger.info(f"Notification email sent to {user.email}: {title}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}")
        return False

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
    from django.conf import settings

    # Rate limiting check
    ip_address = get_client_ip(request)
    cache_key = f"login_attempts:{ip_address}"
    user_agent = request.META.get('HTTP_USER_AGENT', '')
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
            try:
                send_security_alert_email(user, ip_address, user_agent)
            except Exception as e:
                logger.error(f"Failed to send security alert: {str(e)}")
            
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
