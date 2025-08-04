"""
Signal handlers for the website app
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from .models import BlogPost, Contact

@receiver(pre_save, sender=BlogPost)
def create_blog_slug(sender, instance, **kwargs):
    """
    Automatically generate a slug for BlogPost instances if one doesn't exist
    """
    if not instance.slug:
        instance.slug = slugify(instance.title)

@receiver(post_save, sender=Contact)
def handle_new_contact(sender, instance, created, **kwargs):
    """
    Handle actions when a new contact form is submitted
    For example, you could send a notification email to admins
    """
    if created:
        # This is where you could add any additional processing
        # like sending admin notifications, etc.
        pass