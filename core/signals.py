"""
Signal handlers for the core app
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils import timezone

from core.mixins import AppPermissionRequiredMixin

from .models import UserProfile, LoginActivity, Notification

# Signal to create a user profile when a new user is created
@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs):
    profile, created_profile = UserProfile.objects.get_or_create(user=instance)

    # Only send a notification for brand new users
    if created:
        Notification.objects.create(
            user=instance,
            title="Welcome to BlitzTech Electronics!",
            message="Welcome to our platform. If you have any questions, please contact support.",
            type="info",
        )

# Signal for login tracking
@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Track user login and update last login time"""
    # Create login activity record
    LoginActivity.objects.create(
        user=user,
        ip_address=request.META.get('REMOTE_ADDR', None),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    # Update user profile last login
    if hasattr(user, 'profile'):
        user.profile.last_login = timezone.now()
        user.profile.save()

# Signal for logging out
@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """Handle post-logout actions if needed"""
    # This is a placeholder for any future logout tracking needs
    pass

@receiver(post_save, sender=AppPermissionRequiredMixin)
def invalidate_app_permission_cache(sender, instance, **kwargs):
    """Invalidate permission cache when permissions are updated"""
    from core.utils import invalidate_permission_cache
    invalidate_permission_cache(instance.user.id)
