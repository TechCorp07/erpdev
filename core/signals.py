from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils import timezone

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
            notification_type="welcome",  # Changed from type="info" to notification_type="welcome"
        )

# Signal for login tracking
@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Track user login and update last login time"""
    # Create login activity record
    LoginActivity.objects.create(
        user=user,
        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    # Note: last_login is handled automatically by Django's User model
    # No need to manually update user.profile.last_login

# Signal for logging out
@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """Handle post-logout actions if needed"""
    # This is a placeholder for any future logout tracking needs
    pass
