from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
import logging
from .models import (
    EmployeeRole, UserProfile, AppPermission, LoginActivity,
    SecurityLog, SystemSetting, GuestSession, Notification,
    ApprovalRequest, SecurityEvent, UserRole
)

logger = logging.getLogger(__name__)
admin.site.unregister(User)

@admin.register(AppPermission)
class AppPermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'get_role_display', 'app', 'permission_level', 'created_at')
    list_filter = (
        'app', 
        'permission_level', 
        'created_at'
    )
    search_fields = ('role__name', 'role__display_name')
    autocomplete_fields = ['role']
    date_hierarchy = 'created_at'
    
    def get_role_display(self, obj):
        return obj.role.display_name if obj.role else '-'
    get_role_display.short_description = 'Role Name'

@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_user_type', 'timestamp', 'ip_address', 'get_location', 'get_user_agent_summary')
    list_filter = ('timestamp', 'user__profile__user_type')
    search_fields = ('user__username', 'ip_address', 'user_agent', 'user__email')
    readonly_fields = ('user', 'timestamp', 'ip_address', 'user_agent')
    date_hierarchy = 'timestamp'
    
    def get_user_agent_summary(self, obj):
        if obj.user_agent:
            # Extract browser/device info
            agent = obj.user_agent.lower()
            if 'chrome' in agent:
                browser = 'Chrome'
            elif 'firefox' in agent:
                browser = 'Firefox'
            elif 'safari' in agent:
                browser = 'Safari'
            elif 'edge' in agent:
                browser = 'Edge'
            else:
                browser = 'Other'
            
            if 'mobile' in agent:
                device = 'Mobile'
            elif 'tablet' in agent:
                device = 'Tablet'
            else:
                device = 'Desktop'
            
            return f"{browser} ({device})"
        return 'Unknown'
    get_user_agent_summary.short_description = 'Browser/Device'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_user_type(self, obj):
        return obj.user.profile.get_user_type_display() if hasattr(obj.user, 'profile') else '-'
    get_user_type.short_description = 'User Type'
    
    def get_location(self, obj):
        # Placeholder for IP geolocation
        return 'Unknown'
    get_location.short_description = 'Location'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_user_type', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = (
        'notification_type', 
        'is_read',
        'created_at',
        'user__profile__user_type'
    )
    search_fields = ('user__username', 'user__email', 'title', 'message')
    readonly_fields = ('user', 'notification_type', 'title', 'message', 'created_at')
    date_hierarchy = 'created_at'
    
    def get_user_type(self, obj):
        return obj.user.profile.get_user_type_display() if hasattr(obj.user, 'profile') else '-'
    get_user_type.short_description = 'User Type'
    
    def has_add_permission(self, request):
        return False

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    fk_name = 'user'
    can_delete = False
    max_num = 1
    extra = 0  # Don't show extra forms
    
    fields = ('user_type', 'department', 'phone', 'address', 'profile_image')
    
    def get_queryset(self, request):
        """Ensure we get the existing profile if it exists"""
        qs = super().get_queryset(request)
        return qs.select_related('user')
    
    def has_add_permission(self, request, obj=None):
        """Only allow adding if no profile exists"""
        if obj and hasattr(obj, 'profile'):
            return False
        return super().has_add_permission(request, obj)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Standalone UserProfile admin"""
    list_display = (
        'user', 'user_type', 'department', 'phone', 'get_date_joined'
    )
    
    list_filter = (
        'user_type', 
        'department',
        'user__date_joined'
    )
    
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone')
    
    readonly_fields = ('get_date_joined',)
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Basic Information', {
            'fields': ('user_type', 'department', 'phone', 'address', 'profile_image')
        }),
        ('User Account Info', {
            'fields': ('get_date_joined',)
        }),
    )
    
    def get_date_joined(self, obj):
        return obj.user.date_joined if obj.user else None
    get_date_joined.short_description = 'Date Joined'


# Add UserRole inline since AppPermission is role-based now
class UserRoleInline(admin.TabularInline):
    """Inline admin for UserRole"""
    model = UserRole
    fk_name = 'user'
    extra = 0
    fields = ('role', 'assigned_at', 'is_active', 'expires_at')
    readonly_fields = ('assigned_at',)

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, UserRoleInline)
    
    # Enhanced list display
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'get_user_type', 'get_department', 'get_last_login',
        'get_account_status', 'is_staff', 'is_active', 'date_joined'
    )
    
    # Enhanced filtering - removed non-existent fields
    list_filter = (
        'profile__user_type', 
        'profile__department',
        'is_staff', 
        'is_active', 
        'is_superuser', 
        'date_joined'
    )
    
    # Enhanced search
    search_fields = BaseUserAdmin.search_fields + ('profile__phone',)
    
    def get_user_type(self, obj):
        return obj.profile.get_user_type_display() if hasattr(obj, 'profile') else '-'
    get_user_type.short_description = 'User Type'
    
    def get_department(self, obj):
        return obj.profile.get_department_display() if hasattr(obj, 'profile') and obj.profile.department else '-'
    get_department.short_description = 'Department'
    
    def get_last_login(self, obj):
        return obj.last_login.strftime('%Y-%m-%d %H:%M') if obj.last_login else 'Never'
    get_last_login.short_description = 'Last Login'
    
    def save_model(self, request, obj, form, change):
        """Save user and ensure profile exists"""
        super().save_model(request, obj, form, change)
        
        if not hasattr(obj, 'profile'):
            try:
                UserProfile.objects.get_or_create(user=obj)
            except Exception as e:
                logger.error(f"Error ensuring profile for user {obj.username}: {e}")
                
    def get_account_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: red;">Inactive</span>')
        elif obj.is_staff:
            return format_html('<span style="color: green;">Staff</span>')
        else:
            return format_html('<span style="color: blue;">Active</span>')
    get_account_status.short_description = 'Status'


@admin.register(EmployeeRole)
class EmployeeRoleAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'hierarchy_level', 'requires_gm_approval', 'can_assign_roles')
    list_filter = ('hierarchy_level', 'requires_gm_approval', 'can_assign_roles')
    search_fields = ('name', 'display_name', 'description')
    readonly_fields = ('created_at', 'updated_at')


# Add admin for UserRole
@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_by', 'assigned_at', 'is_active')
    list_filter = ('role', 'is_active', 'assigned_at')
    search_fields = ('user__username', 'user__email', 'role__display_name')
    readonly_fields = ('assigned_at',)

class AppPermissionInline(admin.TabularInline):
    """Inline admin for AppPermission"""
    model = AppPermission
    extra = 0
    fields = ('app', 'permission_level', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    """Admin for ApprovalRequest"""
    list_display = (
        'user', 'get_user_type', 'request_type', 'status', 
        'requested_at', 'reviewed_by', 'reviewed_at'
    )
    
    list_filter = (
        'request_type', 'status', 'requested_at', 'reviewed_at',
        'user__profile__user_type'
    )
    
    search_fields = (
        'user__username', 'user__email', 'user__first_name', 'user__last_name',
        'requested_reason', 'business_justification'
    )
    
    readonly_fields = ('requested_at', 'reviewed_at')
    
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'request_type', 'status', 'requested_at')
        }),
        ('Request Details', {
            'fields': ('requested_reason', 'business_justification')
        }),
        ('Review Information', {
            'fields': ('reviewed_by', 'reviewed_at', 'review_notes')
        }),
    )
    
    def get_user_type(self, obj):
        return obj.user.profile.get_user_type_display()
    get_user_type.short_description = 'User Type'
    get_user_type.admin_order_field = 'user__profile__user_type'
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        updated = 0
        for approval_request in queryset.filter(status='pending'):
            approval_request.approve(request.user, 'Bulk approved by admin')
            updated += 1
        
        self.message_user(request, f'Approved {updated} requests.')
    approve_requests.short_description = 'Approve selected requests'
    
    def reject_requests(self, request, queryset):
        updated = 0
        for approval_request in queryset.filter(status='pending'):
            approval_request.reject(request.user, 'Bulk rejected by admin')
            updated += 1
        
        self.message_user(request, f'Rejected {updated} requests.')
    reject_requests.short_description = 'Reject selected requests'

@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    """Admin for SecurityEvent"""
    list_display = (
        'user', 'event_type', 'ip_address', 'timestamp', 'get_details_summary'
    )
    
    list_filter = (
        'event_type', 'timestamp', 'ip_address'
    )
    
    search_fields = (
        'user__username', 'user__email', 'ip_address', 'user_agent'
    )
    
    readonly_fields = ('user', 'event_type', 'ip_address', 'user_agent', 'details', 'timestamp')
    
    date_hierarchy = 'timestamp'
    
    def get_details_summary(self, obj):
        if obj.details:
            summary = []
            for key, value in obj.details.items():
                if len(str(value)) < 50:
                    summary.append(f"{key}: {value}")
            return ', '.join(summary[:3])
        return 'No details'
    get_details_summary.short_description = 'Details Summary'
    
    def has_add_permission(self, request):
        return False  # Security events are created programmatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Security events should not be modified

@admin.register(SecurityLog)
class SecurityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'event_type', 'timestamp', 'ip_address')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__username', 'description', 'ip_address')
    readonly_fields = ('user', 'event_type', 'description', 'ip_address', 'user_agent', 'timestamp')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value_preview', 'category', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active', 'updated_at')
    search_fields = ('key', 'value', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Setting Information', {
            'fields': ('key', 'value', 'category', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def value_preview(self, obj):
        return obj.value[:100] + '...' if len(obj.value) > 100 else obj.value
    value_preview.short_description = 'Value'

@admin.register(GuestSession)
class GuestSessionAdmin(admin.ModelAdmin):
    list_display = ('session_key_preview', 'created_at', 'updated_at', 'is_expired_display')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('session_key',)
    readonly_fields = ('session_key', 'created_at', 'updated_at')
    
    actions = ['cleanup_expired_sessions']
    
    def session_key_preview(self, obj):
        return f"{obj.session_key[:8]}..."
    session_key_preview.short_description = 'Session Key'
    
    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        else:
            return format_html('<span style="color: green;">Active</span>')
    is_expired_display.short_description = 'Status'
    
    @admin.action(description='Clean up expired guest sessions')
    def cleanup_expired_sessions(self, request, queryset):
        count = GuestSession.cleanup_expired_sessions()
        self.message_user(request, f'{count} expired guest sessions cleaned up.')

# Customize Admin Site
admin.site.register(User, UserAdmin)
admin.site.site_header = "BlitzTech Electronics Administration"
admin.site.site_title = "BlitzTech Admin"
admin.site.index_title = "Welcome to BlitzTech Electronics Administration"
