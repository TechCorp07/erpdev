from django.db import models
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.utils.text import slugify

class Category(models.Model):
    """Model for blog and portfolio categories"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class BlogPost(models.Model):
    """Model for blog posts"""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    categories = models.ManyToManyField(Category, related_name='blog_posts', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Service(models.Model):
    """Model for services offered"""
    CATEGORY_CHOICES = (
        ('components', 'Electronic Components'),
        ('software', 'Software Development'),
        ('security', 'Security Systems'),
        ('drone', 'Drone Technology'),
        ('power', 'Power Systems'),
        ('iot', 'IoT Systems'),
        ('research', 'Research & Development'),
        ('pcb', 'PCB Fabrication'),
        ('other', 'Other Services'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Bootstrap icon name (e.g., 'code-slash')")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['category', 'order']
    
    def __str__(self):
        return self.title


class PortfolioItem(models.Model):
    """Model for portfolio items/projects"""
    TYPE_CHOICES = (
        ('security', 'Security Systems'),
        ('drone', 'Drone Technology'),
        ('power', 'Power Systems'),
        ('iot', 'IoT Solutions'),
        ('pcb', 'PCB Design'),
        ('other', 'Other Projects'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='portfolio/')
    categories = models.ManyToManyField(Category, related_name='portfolio_items', blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other')
    client = models.CharField(max_length=200, blank=True)
    url = models.URLField(blank=True, null=True)
    date_completed = models.DateField(blank=True, null=True)
    featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-featured', 'order', '-date_completed']
    
    def __str__(self):
        return self.title


class FAQ(models.Model):
    """Model for frequently asked questions"""
    CATEGORY_CHOICES = (
        ('components', 'Components & Supply'),
        ('security', 'Security Systems'),
        ('iot', 'IoT & Smart Solutions'),
        ('pcb', 'PCB Fabrication'),
        ('power', 'Power Systems'),
        ('payment', 'Orders & Payment'),
        ('contact', 'Contact'),
        ('general', 'General'),
    )
    
    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['category', 'order']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
    
    def __str__(self):
        return self.question


class Contact(models.Model):
    """Model for contact form submissions"""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"


class Testimonial(models.Model):
    """Model for client testimonials"""
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    company = models.CharField(max_length=100)
    image = models.ImageField(upload_to='testimonials/', blank=True, null=True)
    content = models.TextField()
    rating = models.PositiveIntegerField(default=5, choices=[(i, i) for i in range(1, 6)])
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.name} - {self.company}"


class TeamMember(models.Model):
    """Model for team members"""
    name = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    image = models.ImageField(upload_to='team/')
    email = models.EmailField(blank=True)
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    github = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"{self.name} - {self.position}"


class Partner(models.Model):
    """Model for business partners/clients"""
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='partners/')
    url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.name


class CompanyInfo(models.Model):
    """Model for company information that may change over time"""
    name = models.CharField(max_length=100, default="BlitzTech Electronics")
    address = models.CharField(max_length=255, default="904 Premium Close, Mount Pleasant, Business Park, Harare, Zimbabwe")
    phone = models.CharField(max_length=20, default="+263 774 613 020")
    email = models.EmailField(default="sales@blitztechelectronics.co.zw")
    website = models.URLField(default="www.blitztechelectronics.co.zw")
    facebook = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    mission = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    about_us = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Company Information"
        verbose_name_plural = "Company Information"
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        if CompanyInfo.objects.exists() and not self.pk:
            raise ValidationError("Only one company info instance is allowed")
        super().save(*args, **kwargs)
