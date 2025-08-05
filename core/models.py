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
        ('sales', 'Sales and Marketing'),
        ('support', 'Customer Support'),
        ('technical', 'Technical'),
        ('admin', 'Administration'),
        ('procurement', 'Procurement'),
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
    
    # Approval workflow fields
    is_approved = models.BooleanField(default=False, help_text="General account approval status")
    crm_approved = models.BooleanField(default=False, help_text="Approved for CRM access")
    blog_approved = models.BooleanField(default=False, help_text="Approved for blog management")
    shop_approved = models.BooleanField(default=True, help_text="Approved for shopping cart (default true)")
    
    # Approval tracking
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_profiles', help_text="Admin who approved this profile"
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True, help_text="Notes from approver")
    
    # Profile completion tracking
    profile_completed = models.BooleanField(default=False)
    profile_completion_date = models.DateTimeField(null=True, blank=True)
    required_fields_completed = models.JSONField(default=list, blank=True)
    
    # Enhanced security fields
    two_factor_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, blank=True)
    last_security_check = models.DateTimeField(null=True, blank=True)
    
    # Social login tracking
    is_social_account = models.BooleanField(default=False)
    social_provider = models.CharField( max_length=20, blank=True, 
        choices=[('google', 'Google'), ('facebook', 'Facebook'), ('manual', 'Manual Registration')])
    social_verified = models.BooleanField(default=False)
    
    # Business information (for customers and bloggers)
    company_name = models.CharField(max_length=200, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    business_registration = models.CharField(max_length=100, blank=True)
    
    # NEW: Enhanced notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    approval_notifications = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=False)
    theme_preference = models.CharField(max_length=10, default='light', choices=[('light', 'Light'), ('dark', 'Dark'), ('auto', 'Auto')])
    allow_profile_discovery = models.BooleanField(default=True)
    
    # Billing information
    billing_address = models.TextField(blank=True)
    shipping_address = models.TextField(blank=True)
    same_as_billing = models.BooleanField(default=True)
    
    # Security enhancements
    last_password_change = models.DateTimeField(blank=True, null=True)
    login_attempts = models.PositiveSmallIntegerField(default=0)
    account_locked_until = models.DateTimeField(blank=True, null=True)
    requires_password_change = models.BooleanField(default=False)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    password_history = models.JSONField(default=list, blank=True)  # Store hashed passwords to prevent reuse
    
    class Meta:
        ordering = ['user__first_name', 'user__last_name']
        indexes = [
            models.Index(fields=['user_type', 'is_approved']),
            models.Index(fields=['crm_approved']),
            models.Index(fields=['profile_completed']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_user_type_display()})"
    
    def needs_approval_for(self, access_type):
        """Check if user needs approval for specific access type"""
        approval_mapping = {
            'crm': not self.crm_approved,
            'blog': not self.blog_approved and self.user_type == 'blogger',
            'shop': not self.shop_approved,
        }
        return approval_mapping.get(access_type, False)

    def approve_for_access(self, access_type, approved_by_user, notes=""):
        """Approve user for specific access type"""
        from django.utils import timezone
        
        if access_type == 'crm':
            self.crm_approved = True
        elif access_type == 'blog':
            self.blog_approved = True
        elif access_type == 'shop':
            self.shop_approved = True
        elif access_type == 'general':
            self.is_approved = True
            
        self.approved_by = approved_by_user
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.save()
        
        # Create notification
        from .utils import create_notification
        create_notification(
            user=self.user,
            title=f"Access Approved: {access_type.upper()}",
            message=f"Your access to {access_type} has been approved. You can now use this feature.",
            notification_type='success'
        )
        
        # Log the approval
        import logging
        logger = logging.getLogger('core.authentication')
        logger.info(f"User {self.user.username} approved for {access_type} by {approved_by_user.username}")

    def check_profile_completion(self):
        """Check if profile is complete based on required fields"""
        from django.conf import settings
        
        required_fields = getattr(settings, 'PROFILE_COMPLETION_REQUIRED_FIELDS', [])
        completed_fields = []
        
        for field in required_fields:
            if hasattr(self.user, field):
                if getattr(self.user, field):
                    completed_fields.append(field)
            elif hasattr(self, field):
                if getattr(self, field):
                    completed_fields.append(field)
        
        self.required_fields_completed = completed_fields
        self.profile_completed = len(completed_fields) == len(required_fields)
        
        if self.profile_completed and not self.profile_completion_date:
            from django.utils import timezone
            self.profile_completion_date = timezone.now()
        
        self.save(update_fields=['required_fields_completed', 'profile_completed', 'profile_completion_date'])
        return self.profile_completed

    def get_incomplete_fields(self):
        """Get list of incomplete required fields"""
        from django.conf import settings
        
        required_fields = getattr(settings, 'PROFILE_COMPLETION_REQUIRED_FIELDS', [])
        incomplete_fields = []
        
        for field in required_fields:
            value = None
            if hasattr(self.user, field):
                value = getattr(self.user, field)
            elif hasattr(self, field):
                value = getattr(self, field)
            
            if not value:
                incomplete_fields.append(field)
        
        return incomplete_fields

    def can_access_crm(self):
        """Check if user can access CRM"""
        if self.user_type == 'employee':
            return True  # Employees get access based on permissions
        return self.crm_approved and self.profile_completed

    def can_access_shop(self):
        """Check if user can access shopping cart"""
        return self.shop_approved  # Shopping is less restrictive

    def can_access_blog(self):
        """Check if blogger can manage blog content"""
        return self.user_type == 'blogger' and self.blog_approved and self.profile_completed

    @property
    def approval_status_display(self):
        """Human-readable approval status"""
        if self.user_type == 'employee':
            return "Employee Account"
        
        statuses = []
        if self.crm_approved:
            statuses.append("CRM")
        if self.blog_approved and self.user_type == 'blogger':
            statuses.append("Blog")
        if self.shop_approved:
            statuses.append("Shop")
            
        return f"Approved: {', '.join(statuses)}" if statuses else "Pending Approval"

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


class ApprovalRequest(models.Model):
    """Track approval requests for users"""
    
    REQUEST_TYPES = (
        ('crm', 'CRM Access'),
        ('blog', 'Blog Management'),
        ('shop', 'Shop Access'),
        ('general', 'General Account'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='approval_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Request details
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_reason = models.TextField(blank=True, help_text="Why user needs this access")
    business_justification = models.TextField(blank=True)
    
    # Approval details
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_approval_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-requested_at']
        unique_together = ('user', 'request_type', 'status')  # Prevent duplicate pending requests
    
    def __str__(self):
        return f"{self.user.username} - {self.get_request_type_display()} ({self.status})"

    def approve(self, reviewer, notes=""):
        """Approve the request"""
        from django.utils import timezone
        
        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Apply the approval to user profile
        self.user.profile.approve_for_access(self.request_type, reviewer, notes)
        
        return True

    def reject(self, reviewer, notes=""):
        """Reject the request"""
        from django.utils import timezone
        
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        self.save()
        
        # Create notification for user
        from .utils import create_notification
        create_notification(
            user=self.user,
            title=f"Access Request Rejected: {self.get_request_type_display()}",
            message=f"Your request for {self.get_request_type_display()} has been rejected. Reason: {notes}",
            notification_type='warning'
        )
        
        return True


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


class SecurityEvent(models.Model):
    """Log security-related events"""
    
    EVENT_TYPES = (
        ('login_success', 'Successful Login'),
        ('login_failure', 'Failed Login'),
        ('password_change', 'Password Changed'),
        ('profile_update', 'Profile Updated'),
        ('permission_change', 'Permissions Modified'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('account_lockout', 'Account Locked'),
        ('social_login', 'Social Login'),
        ('approval_granted', 'Approval Granted'),
        ('approval_rejected', 'Approval Rejected'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_events', null=True, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]
    
    def __str__(self):
        username = self.user.username if self.user else 'Anonymous'
        return f"{username} - {self.get_event_type_display()} at {self.timestamp}"


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
