from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.forms import ValidationError

class UserProfile(models.Model):
    """Enhanced user profile with quote management capabilities"""
    USER_TYPES = (
        ('customer', 'Customer'),  # For shopping cart
        ('blogger', 'Blogger'),    # For blog management
        ('employee', 'Employee'),  # General staff
        ('sales_rep', 'Sales Representative'),  # NEW: For quote creation
        ('sales_manager', 'Sales Manager'),     # NEW: For quote approval
        ('blitzhub_admin', 'BlitzHub Admin'),  # Content/business admin
        ('it_admin', 'IT Admin'),  # Technical admin
    )
    
    DEPARTMENTS = (
        ('sales', 'Sales'),
        ('support', 'Customer Support'),
        ('technical', 'Technical'),
        ('admin', 'Administration'),
        ('marketing', 'Marketing'),
        ('content', 'Content'),
        ('warehouse', 'Warehouse'),
        ('hr', 'Human Resources'),
        ('finance', 'Finance'),
        ('other', 'Other'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    department = models.CharField(max_length=20, choices=DEPARTMENTS, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(blank=True, null=True)
    email_notifications = models.BooleanField(default=True)
    theme_preference = models.CharField(max_length=10, default='light', choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')])
    allow_profile_discovery = models.BooleanField(default=True)
    
    # Security enhancements
    last_password_change = models.DateTimeField(blank=True, null=True)
    login_attempts = models.PositiveSmallIntegerField(default=0)
    account_locked_until = models.DateTimeField(blank=True, null=True)
    requires_password_change = models.BooleanField(default=False)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    password_history = models.JSONField(default=list, blank=True)  # Store hashed passwords to prevent reuse
    
    class Meta:
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_user_type_display()}"
    
    @property
    def has_shop_access(self):
        """Check if user has access to shop management"""
        return self.user_type in ['customer', 'blitzhub_admin', 'it_admin']
    
    @property
    def has_blog_access(self):
        """Check if user has access to blog management"""
        return self.user_type in ['blogger', 'blitzhub_admin', 'it_admin']
    
    @property
    def has_employee_dashboard_access(self):
        """Check if user has access to employee dashboard"""
        return self.user_type in ['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin']
    
    @property
    def is_employee(self):
        """Check if user is an employee (includes sales staff)"""
        return self.user_type in ['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin']
    
    @property
    def is_manager(self):
        """Check if user is a manager"""
        return self.user_type in ['sales_manager', 'blitzhub_admin', 'it_admin']
    
    @property
    def is_admin(self):
        """Check if user is any type of admin"""
        return self.user_type in ['blitzhub_admin', 'it_admin']
    
    @property
    def is_it_admin(self):
        """Check if user is IT admin"""
        return self.user_type == 'it_admin'
    
    @property
    def can_manage_quotes(self):
        """Check if user can manage quotes"""
        return self.user_type in ['sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin']
    
    @property
    def can_approve_quotes(self):
        """Check if user can approve quotes"""
        return self.user_type in ['sales_manager', 'blitzhub_admin', 'it_admin']
    
    @property
    def is_account_locked(self):
        """Check if the account is temporarily locked due to failed login attempts"""
        if not self.account_locked_until:
            return False
        return timezone.now() < self.account_locked_until
    
    @property
    def days_since_password_change(self):
        """Calculate days since the last password change"""
        if not self.last_password_change:
            return (timezone.now() - self.date_joined).days
        return (timezone.now() - self.last_password_change).days
    
    def lock_account(self, minutes=30):
        """Lock the account for the specified time due to security concerns"""
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=minutes)
        self.save(update_fields=['account_locked_until'])
    
    def unlock_account(self):
        """Manually unlock a locked account"""
        self.account_locked_until = None
        self.failed_login_count = 0
        self.save(update_fields=['account_locked_until', 'failed_login_count'])
    
    def record_password_change(self, password_hash):
        """Record a password change and store the hashed password in history"""
        self.last_password_change = timezone.now()
        self.requires_password_change = False
        
        # Store password hash in history (limit to last 5)
        history = self.password_history
        history.append({
            'hash': password_hash,
            'date': self.last_password_change.isoformat()
        })
        
        # Keep only the last 5 passwords
        if len(history) > 5:
            history = history[-5:]
        
        self.password_history = history
        self.save(update_fields=['last_password_change', 'requires_password_change', 'password_history'])
    
    def has_used_password_before(self, password_hash):
        """Check if a password has been used before"""
        if not self.password_history:
            return False
        
        for entry in self.password_history:
            if entry.get('hash') == password_hash:
                return True
        return False


class AppPermission(models.Model):
    """Enhanced user permissions for different applications including quotes"""
    APP_CHOICES = (
        ('crm', 'CRM System'),
        ('inventory', 'Inventory Management'),
        ('shop', 'Shop Management'),
        ('website', 'Website Management'),
        ('blog', 'Blog Management'),
        ('hr', 'HR Management'),
        ('admin', 'Admin Panel'),
        # NEW: Quote-related permissions
        ('quotes', 'Quote Management'),
        ('financial', 'Financial Data'),
        ('reports', 'Reporting System'),
    )
    
    PERMISSION_LEVELS = (
        ('view', 'View Only'),
        ('edit', 'Create and Edit'),
        ('admin', 'Full Admin Access'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='app_permissions')
    app = models.CharField(max_length=20, choices=APP_CHOICES)
    permission_level = models.CharField(max_length=10, choices=PERMISSION_LEVELS, default='view')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'app')
        ordering = ['app', 'permission_level']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_app_display()} ({self.get_permission_level_display()})"


class LoginActivity(models.Model):
    """Track user login activity for security monitoring"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_activities')
    login_datetime = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-login_datetime']
        verbose_name_plural = "Login Activities"
    
    def __str__(self):
        return f"{self.user.username} - {self.login_datetime.strftime('%Y-%m-%d %H:%M:%S')}"


class Notification(models.Model):
    """Enhanced user notifications system with quote support"""
    NOTIFICATION_TYPES = (
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('quote', 'Quote Update'),  # NEW: Quote-specific notifications
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)
    
    # NEW: Optional action URL for interactive notifications
    action_url = models.URLField(blank=True, null=True, help_text="Optional URL for notification action")
    action_text = models.CharField(max_length=50, blank=True, help_text="Text for action button")
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])


class SessionActivity(models.Model):
    """Track user session activity"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_activities')
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.username} - {self.session_key[:8]}..."


class SecurityLog(models.Model):
    """Log security-related events"""
    EVENT_TYPES = (
        ('login_success', 'Successful Login'),
        ('login_failed', 'Failed Login'),
        ('password_changed', 'Password Changed'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('permission_changed', 'Permission Changed'),
        ('suspicious_activity', 'Suspicious Activity'),
    )
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        user_info = self.user.username if self.user else 'Anonymous'
        return f"{user_info} - {self.get_event_type_display()} - {self.timestamp}"


# Enhanced system settings for quote system integration
class SystemSetting(models.Model):
    """Enhanced system-wide configuration settings including quote settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # NEW: Category for organizing settings
    category = models.CharField(max_length=50, default='general', help_text="Category for organizing settings")
    
    class Meta:
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.key}: {self.value[:50]}"
    
    @classmethod
    def get_setting(cls, key, default=None):
        """Get a setting value by key"""
        try:
            setting = cls.objects.get(key=key, is_active=True)
            return setting.value
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key, value, description='', category='general'):
        """Set a setting value"""
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': value,
                'description': description,
                'category': category,
                'is_active': True
            }
        )
        return setting


# NEW: Helper function to set up default quote permissions
def setup_default_quote_permissions():
    """
    Set up default quote permissions for existing users based on their roles.
    This function should be called during migration or setup.
    """
    from django.db import transaction
    
    # Default permission mappings based on user type
    permission_mappings = {
        'sales_rep': {'quotes': 'edit', 'financial': 'view', 'reports': 'view'},
        'sales_manager': {'quotes': 'admin', 'financial': 'edit', 'reports': 'admin'},
        'blitzhub_admin': {'quotes': 'admin', 'financial': 'admin', 'reports': 'admin'},
        'it_admin': {'quotes': 'admin', 'financial': 'view', 'reports': 'admin'},
        'employee': {'quotes': 'view', 'financial': 'view', 'reports': 'view'},
    }
    
    with transaction.atomic():
        for user_profile in UserProfile.objects.all():
            user_type = user_profile.user_type
            if user_type in permission_mappings:
                permissions = permission_mappings[user_type]
                
                for app, level in permissions.items():
                    AppPermission.objects.update_or_create(
                        user=user_profile.user,
                        app=app,
                        defaults={'permission_level': level}
                    )

# NEW: Quote system settings helper
def initialize_quote_system_settings():
    """
    Initialize default system settings for the quote system.
    This ensures the quote system has all necessary configuration.
    """
    quote_settings = [
        # Company Information
        ('COMPANY_NAME', 'BlitzTech Electronics', 'Company name for quotes and emails', 'company'),
        ('COMPANY_ADDRESS', 'Harare, Zimbabwe', 'Company address for quotes', 'company'),
        ('COMPANY_PHONE', '+263 XX XXX XXXX', 'Company phone number', 'company'),
        ('COMPANY_EMAIL', 'info@blitztech.co.zw', 'Company email address', 'company'),
        ('COMPANY_WEBSITE', 'www.blitztech.co.zw', 'Company website', 'company'),
        
        # Quote System Configuration
        ('DEFAULT_QUOTE_VALIDITY_DAYS', '30', 'Default validity period for quotes in days', 'quotes'),
        ('DEFAULT_PAYMENT_TERMS', '30', 'Default payment terms in days', 'quotes'),
        ('DEFAULT_TAX_RATE', '15.00', 'Default tax rate percentage (Zimbabwe VAT)', 'quotes'),
        ('HIGH_VALUE_QUOTE_THRESHOLD', '10000.00', 'Amount above which quotes require approval', 'quotes'),
        ('HIGH_DISCOUNT_THRESHOLD', '20.00', 'Discount percentage above which quotes require approval', 'quotes'),
        
        # Email Settings
        ('QUOTE_EMAIL_FROM', 'quotes@blitztech.co.zw', 'From email for quote emails', 'email'),
        ('QUOTE_EMAIL_CC_MANAGEMENT', '', 'Email addresses to CC on high-value quotes (comma-separated)', 'email'),
        ('QUOTE_EMAIL_SIGNATURE', 'Best regards,\nBlitzTech Electronics Team', 'Email signature for quote emails', 'email'),
        
        # PDF Settings
        ('PDF_SHOW_PROFIT_ANALYSIS', 'false', 'Show profit analysis in PDFs (true/false)', 'pdf'),
        ('PDF_WATERMARK', '', 'Watermark text for quote PDFs', 'pdf'),
        ('PDF_FOOTER_TEXT', 'Thank you for your business!', 'Footer text for quote PDFs', 'pdf'),
    ]
    
    for key, value, description, category in quote_settings:
        SystemSetting.set_setting(key, value, description, category)


# Model for handling guest sessions (for shopping cart)
class GuestSession(models.Model):
    """Handle guest user sessions for shopping cart functionality"""
    session_key = models.CharField(max_length=40, unique=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Guest Session: {self.session_key[:8]}..."
    
    def is_expired(self, expiry_hours=24):
        """Check if the guest session has expired"""
        expiry_time = self.updated_at + timezone.timedelta(hours=expiry_hours)
        return timezone.now() > expiry_time
    
    @classmethod
    def cleanup_expired_sessions(cls, expiry_hours=24):
        """Clean up expired guest sessions"""
        cutoff_time = timezone.now() - timezone.timedelta(hours=expiry_hours)
        expired_sessions = cls.objects.filter(updated_at__lt=cutoff_time)
        count = expired_sessions.count()
        expired_sessions.delete()
        return count

class AuditLog(models.Model):
    ACTIONS = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('permission_change', 'Permission Change'),
        ('security', 'Security Event'),
        ('api', 'API Request'),
        ('custom', 'Custom'),
    ]
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=30, choices=ACTIONS)
    description = models.TextField()
    object_type = models.CharField(max_length=100, blank=True, help_text="Type of the object affected, e.g. 'Quote', 'UserProfile'")
    object_id = models.CharField(max_length=100, blank=True, help_text="ID of the object affected")
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    extra_data = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp}] {self.user} {self.action}: {self.description}"
