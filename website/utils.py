"""
Utility functions for the website app
"""
import os
import uuid
from django.utils.text import slugify
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

def get_unique_slug(instance, field_name, new_slug=None):
    """
    Create a unique slug for a model instance
    
    Args:
        instance: Model instance
        field_name: Name of the field to use for slug generation (e.g., 'title')
        new_slug: Optional custom slug to use
        
    Returns:
        A unique slug string
    """
    if new_slug:
        slug = new_slug
    else:
        slug = slugify(getattr(instance, field_name))
    
    # Get the model class
    model_class = instance.__class__
    
    # Check if slug already exists
    slug_exists = model_class.objects.filter(slug=slug).exists()
    
    if slug_exists:
        # If slug exists, create a new unique slug
        unique_slug = f"{slug}-{uuid.uuid4().hex[:8]}"
        return get_unique_slug(instance, field_name, new_slug=unique_slug)
    
    return slug

def resize_image(image_field, max_width=800, max_height=800, quality=85):
    """
    Resize an image field to the specified dimensions
    
    Args:
        image_field: ImageField instance
        max_width: Maximum width for the resized image
        max_height: Maximum height for the resized image
        quality: JPEG compression quality (0-100)
        
    Returns:
        The resized image as a ContentFile
    """
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

def format_phone_number(phone):
    """
    Format a phone number for display
    
    Args:
        phone: Phone number string
        
    Returns:
        Formatted phone number
    """
    # Remove any non-digit characters
    digits = ''.join(c for c in phone if c.isdigit())
    
    # Format based on the number of digits
    if len(digits) == 10:  # US phone number
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':  # US with country code
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    else:
        return phone  # Return original if not recognized format