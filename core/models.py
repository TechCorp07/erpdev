from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.hashers import make_password
import json
import logging


logger = logging.getLogger('core.authentication')

class UserProfile(models.Model):
    """Clean user profile with clear user type separation"""
    
    # CLEAN: Only 3 main user types as requested
    USER_TYPES = (
        ('employee', 'Employee'),      # Internal staff
        ('blogger', 'Blogger'),        # Content creators (can also be customers)
        ('customer', 'Customer'),      # Shoppers (can also be bloggers)
    )
    
    DEPARTMENTS = (
        ('sales', 'Sales and Marketing'),
        ('support', 'Customer Support'),
        ('technical', 'Technical'),
        ('admin', 'Administration'),
        ('procurement', 'Procurement'),
        ('finance', 'Finance/Accounting'),
        ('it', 'IT/Systems'),
        ('other', 'Other'),
    )
    
    # Core Fields
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='customer')
    
    # Employee-specific fields
    department = models.CharField(max_length=20, choices=DEPARTMENTS, blank=True, null=True)
    
    # Contact Information
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    
    # Business Information (for customers)
    company_name = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=50, blank=True)
    business_registration = models.CharField(max_length=100, blank=True)
    
    # Approval Status (simplified)
    is_approved = models.BooleanField(default=False, help_text='General account approval')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_profiles')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Profile Completion
    profile_completed = models.BooleanField(default=False)
    profile_completion_date = models.DateTimeField(null=True, blank=True)
    
    # Social Authentication
    is_social_account = models.BooleanField(default=False)
    social_provider = models.CharField(max_length=20, choices=[
        ('google', 'Google'),
        ('facebook', 'Facebook'),
        ('manual', 'Manual Registration')
    ], blank=True)
    
    # Security Fields
    two_factor_enabled = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(auto_now_add=True)
    requires_password_change = models.BooleanField(default=False)
    failed_login_count = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    password_history = models.JSONField(default=list, blank=True)
    
    # Notification Preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_type', 'is_approved']),
            models.Index(fields=['department']),
            models.Index(fields=['profile_completed']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_user_type_display()})"
    
    @property
    def is_employee(self):
        return self.user_type == 'employee'
    
    @property
    def is_blogger(self):
        return self.user_type == 'blogger'
    
    @property
    def is_customer(self):
        return self.user_type == 'customer'
    
    @property
    def is_account_locked(self):
        """Check if account is currently locked"""
        if not self.account_locked_until:
            return False
        return timezone.now() < self.account_locked_until

    def check_profile_completion(self):
        """Check if profile is complete based on user type"""
        required_fields = ['user.first_name', 'user.last_name', 'user.email']
        
        if self.is_employee:
            required_fields.extend(['department', 'phone'])
        elif self.is_customer:
            required_fields.extend(['phone'])
        
        completed = all(self.get_field_value(field) for field in required_fields)
        
        if completed and not self.profile_completed:
            self.profile_completed = True
            self.profile_completion_date = timezone.now()
            self.save(update_fields=['profile_completed', 'profile_completion_date'])
        
        return completed
    
    def get_field_value(self, field_path):
        """Helper to get nested field values"""
        obj = self
        for field in field_path.split('.'):
            obj = getattr(obj, field, None)
            if obj is None:
                return None
        return obj
    
    def add_password_to_history(self, password_hash):
        """Add password to history for reuse prevention"""
        if not self.password_history:
            self.password_history = []
        
        # Keep last 5 passwords
        self.password_history.append({
            'hash': password_hash,
            'created_at': timezone.now().isoformat()
        })
        
        if len(self.password_history) > 5:
            self.password_history = self.password_history[-5:]
        
        self.last_password_change = timezone.now()
        self.requires_password_change = False
        self.save(update_fields=['last_password_change', 'requires_password_change', 'password_history'])
    
    def has_used_password_before(self, password_hash):
        """Check if password has been used before"""
        if not self.password_history:
            return False
        return any(entry.get('hash') == password_hash for entry in self.password_history)

    def lock_account(self, minutes=30):
        """Lock this account for specified duration"""
        from django.utils import timezone
        from datetime import timedelta
        
        self.account_locked_until = timezone.now() + timedelta(minutes=minutes)
        self.save(update_fields=['account_locked_until'])
        
        # Log the account lock
        from .utils import log_security_event
        log_security_event(
            user=self.user,
            event_type='account_lockout',
            description=f'Account locked for {minutes} minutes',
            ip_address='127.0.0.1',  # Placeholder IP, replace with actual if available
            details={'duration_minutes': minutes}
        )
    
    def unlock_account(self):
        """Unlock this account"""
        self.account_locked_until = None
        self.failed_login_count = 0
        self.save(update_fields=['account_locked_until', 'failed_login_count'])
    
class EmployeeRole(models.Model):
    """Clean employee roles system - separate from user types"""
    
    # The 6 distinct roles as requested
    ROLE_TYPES = (
        ('system_admin', 'System Administrator'),
        ('business_owner', 'Business Owner/GM'), 
        ('sales_manager', 'Sales Manager'),
        ('procurement_officer', 'Procurement Officer'),
        ('service_tech', 'Service Technician + Inventory Controller'),
        ('accounting', 'Accounting/Finance'),
    )
    
    # Role hierarchy levels for permission inheritance
    HIERARCHY_LEVELS = (
        ('level_1', 'System Administrator'),     # Highest
        ('level_2', 'Business Owner/GM'),
        ('level_3', 'Department Managers'),
        ('level_4', 'Officers and Specialists'),
        ('level_5', 'Technicians'),             # Lowest
    )
    
    name = models.CharField(max_length=30, choices=ROLE_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    hierarchy_level = models.CharField(max_length=10, choices=HIERARCHY_LEVELS)
    
    # Security settings
    requires_gm_approval = models.BooleanField(default=False, help_text='Requires GM approval for sensitive operations')
    can_assign_roles = models.BooleanField(default=False, help_text='Can assign/merge roles to other users')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['hierarchy_level', 'name']
    
    def __str__(self):
        return self.get_name_display()


class UserRole(models.Model):
    """Many-to-many relationship for employee role assignments"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_roles')
    role = models.ForeignKey(EmployeeRole, on_delete=models.CASCADE, related_name='users')
    
    # Assignment tracking
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='role_assignments_made')
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Optional: temporary role assignments
    expires_at = models.DateTimeField(null=True, blank=True, help_text='Leave blank for permanent assignment')
    
    class Meta:
        unique_together = ('user', 'role')
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.get_name_display()}"


class AppPermission(models.Model):
    """Clean application permissions - role-based, not user-based"""
    
    APP_CHOICES = (
        ('crm', 'CRM System'),
        ('inventory', 'Inventory Management'),
        ('shop', 'Shop Management'),
        ('website', 'Website Management'),
        ('blog', 'Blog Management'),
        ('hr', 'HR Management'),
        ('admin', 'Admin Panel'),
        ('quotes', 'Quote Management'),
        ('financial', 'Financial Data'),
        ('reports', 'Reporting System'),
    )
    
    PERMISSION_LEVELS = (
        ('view', 'View Only'),
        ('edit', 'Create and Edit'),
        ('admin', 'Full Admin Access'),
    )
    
    # CLEAN: Permission assigned to role, not user directly
    role = models.ForeignKey(EmployeeRole, on_delete=models.CASCADE, related_name='app_permissions')
    app = models.CharField(max_length=20, choices=APP_CHOICES)
    permission_level = models.CharField(max_length=10, choices=PERMISSION_LEVELS, default='view')
    
    # Optional: specific restrictions or exceptions
    restrictions = models.JSONField(default=dict, blank=True, help_text='Specific restrictions within the app')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('role', 'app')
        ordering = ['role', 'app', 'permission_level']
    
    def __str__(self):
        return f"{self.role.get_name_display()} - {self.get_app_display()} ({self.get_permission_level_display()})"


class LoginActivity(models.Model):
    """Track user login activity for security"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_activities')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    success = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]


class SecurityLog(models.Model):
    """Security events and audit trail"""
    EVENT_TYPES = (
        ('login_success', 'Successful Login'),
        ('login_failed', 'Failed Login'),
        ('password_change', 'Password Changed'),
        ('role_assigned', 'Role Assigned'),
        ('permission_changed', 'Permission Modified'),
        ('account_locked', 'Account Locked'),
        ('suspicious_activity', 'Suspicious Activity'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='security_logs')
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    additional_data = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
        ]


class Notification(models.Model):
    """Clean notification system"""
    NOTIFICATION_TYPES = (
        ('security', 'Security Alert'),
        ('role_change', 'Role Assignment'),
        ('approval', 'Approval Request'),
        ('system', 'System Notification'),
        ('welcome', 'Welcome Message'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]


# SIGNALS
def initialize_default_roles():
    """Initialize the 6 default employee roles"""
    default_roles = [
        {
            'name': 'system_admin',
            'display_name': 'System Administrator',
            'description': 'Full system access with GM approval for sensitive operations',
            'hierarchy_level': 'level_1',
            'requires_gm_approval': True,
            'can_assign_roles': True,
        },
        {
            'name': 'business_owner',
            'display_name': 'Business Owner/GM',
            'description': 'Complete control over entire system',
            'hierarchy_level': 'level_2',
            'requires_gm_approval': False,
            'can_assign_roles': True,
        },
        {
            'name': 'sales_manager',
            'display_name': 'Sales Manager',
            'description': 'Sales and marketing management',
            'hierarchy_level': 'level_3',
            'requires_gm_approval': False,
            'can_assign_roles': False,
        },
        {
            'name': 'procurement_officer',
            'display_name': 'Procurement Officer',
            'description': 'Procurement and purchasing management',
            'hierarchy_level': 'level_4',
            'requires_gm_approval': False,
            'can_assign_roles': False,
        },
        {
            'name': 'service_tech',
            'display_name': 'Service Technician + Inventory Controller',
            'description': 'Technical services and inventory management',
            'hierarchy_level': 'level_5',
            'requires_gm_approval': False,
            'can_assign_roles': False,
        },
        {
            'name': 'accounting',
            'display_name': 'Accounting/Finance',
            'description': 'Financial management and accounting',
            'hierarchy_level': 'level_4',
            'requires_gm_approval': False,
            'can_assign_roles': False,
        },
    ]
    
    for role_data in default_roles:
        EmployeeRole.objects.get_or_create(
            name=role_data['name'],
            defaults=role_data
        )
    
    logger.info("Default employee roles initialized")

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
        ('COMPANY_EMAIL', 'info@blitztechelectronics.co.zw', 'Company email address', 'company'),
        ('COMPANY_WEBSITE', 'www.blitztechelectronics.co.zw', 'Company website', 'company'),
        
        # Quote System Configuration
        ('DEFAULT_QUOTE_VALIDITY_DAYS', '30', 'Default validity period for quotes in days', 'quotes'),
        ('DEFAULT_PAYMENT_TERMS', '30', 'Default payment terms in days', 'quotes'),
        ('DEFAULT_TAX_RATE', '15.00', 'Default tax rate percentage (Zimbabwe VAT)', 'quotes'),
        ('HIGH_VALUE_QUOTE_THRESHOLD', '10000.00', 'Amount above which quotes require approval', 'quotes'),
        ('HIGH_DISCOUNT_THRESHOLD', '20.00', 'Discount percentage above which quotes require approval', 'quotes'),
        
        # Email Settings
        ('QUOTE_EMAIL_FROM', 'quotes@blitztechelectronics.co.zw', 'From email for quote emails', 'email'),
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
