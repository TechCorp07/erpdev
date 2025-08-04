from decimal import Decimal
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.db import transaction
from django.utils import timezone
from .models import (
    UserProfile, AppPermission, LoginActivity, Notification, 
    SecurityLog, SessionActivity, SystemSetting, GuestSession
)
from .utils import create_notification, create_bulk_notifications, invalidate_permission_cache
from django.db.models import Q, Count, Sum


# Enhanced UserProfile Inline with Quote Capabilities
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                ('user_type', 'department'),
                ('phone', 'address'),
                'profile_image',
            )
        }),
        ('Security Settings', {
            'fields': (
                ('requires_password_change', 'account_locked_until'),
                ('last_password_change', 'failed_login_count'),
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('last_password_change', 'failed_login_count', 'account_locked_until')
    
    def has_add_permission(self, request, obj):
        return obj is not None
    
    def get_readonly_fields(self, request, obj=None):
        # Only superusers can change user_type and critical security fields
        if not request.user.is_superuser:
            return self.readonly_fields + ('user_type', 'requires_password_change')
        return self.readonly_fields

# Enhanced User Admin with Quote Management
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    
    # Enhanced list display with quote statistics
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'get_user_type', 'get_department', 'get_last_login',
        'get_quote_stats', 'get_account_status', 'is_staff', 'is_active'
    )
    
    # Enhanced filtering including quote-related filters
    list_filter = (
        'profile__user_type', 
        'profile__department',
        'is_staff', 
        'is_active', 
        'date_joined',
        'profile__requires_password_change',
    )
    
    # Enhanced search including quote-related fields
    search_fields = (
        'username', 'email', 'first_name', 'last_name', 
        'profile__phone', 'profile__department'
    )
    
    # Enhanced actions including quote-related bulk operations
    actions = [
        'create_employee_accounts',
        'assign_crm_permissions',
        'assign_inventory_permissions',
        'assign_quote_permissions',  # NEW
        'assign_sales_rep_role',     # NEW
        'assign_sales_manager_role', # NEW
        'reset_passwords',
        'unlock_accounts',
        'send_bulk_notification',
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('profile').annotate(
            quote_count=Count('created_quotes', distinct=True),
            total_quote_value=Sum('created_quotes__total_amount')
        )
    
    def get_user_type(self, obj):
        if hasattr(obj, 'profile'):
            user_type = obj.profile.user_type
            colors = {
                'customer': 'blue',
                'blogger': 'green', 
                'employee': 'orange',
                'sales_rep': 'purple',      # NEW
                'sales_manager': 'indigo',  # NEW
                'blitzhub_admin': 'red',
                'it_admin': 'black'
            }
            color = colors.get(user_type, 'gray')
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                obj.profile.get_user_type_display()
            )
        return '-'
    get_user_type.short_description = 'User Type'
    get_user_type.admin_order_field = 'profile__user_type'
    
    def get_department(self, obj):
        if hasattr(obj, 'profile') and obj.profile.department:
            return obj.profile.get_department_display()
        return '-'
    get_department.short_description = 'Department'
    get_department.admin_order_field = 'profile__department'
    
    def get_last_login(self, obj):
        if hasattr(obj, 'profile') and obj.profile.last_login:
            return obj.profile.last_login.strftime('%Y-%m-%d %H:%M')
        return 'Never'
    get_last_login.short_description = 'Last Login'
    get_last_login.admin_order_field = 'profile__last_login'
    
    # NEW: Quote statistics in admin
    def get_quote_stats(self, obj):
        if hasattr(obj, 'profile') and obj.profile.can_manage_quotes:
            quote_count = getattr(obj, 'quote_count', 0)
            total_value = getattr(obj, 'total_quote_value', Decimal('0.00')) or Decimal('0.00')
            
            if quote_count > 0:
                return format_html(
                    '<div title="Quotes: {} | Total Value: ${:,.2f}">'
                    '<strong>{}</strong> quotes<br/>'
                    '<small>${:,.0f}</small>'
                    '</div>',
                    quote_count, total_value, quote_count, total_value
                )
            else:
                return format_html('<small>No quotes</small>')
        return '-'
    get_quote_stats.short_description = 'Quote Activity'
    
    def get_account_status(self, obj):
        if hasattr(obj, 'profile'):
            if obj.profile.is_account_locked:
                return format_html('<span style="color: red;">🔒 Locked</span>')
            elif obj.profile.requires_password_change:
                return format_html('<span style="color: orange;">⚠️ Password Reset Required</span>')
            else:
                return format_html('<span style="color: green;">✅ Active</span>')
        return '-'
    get_account_status.short_description = 'Account Status'
    
    # Enhanced Custom Actions
    @admin.action(description='Convert selected users to employees')
    def create_employee_accounts(self, request, queryset):
        count = 0
        with transaction.atomic():
            for user in queryset:
                if hasattr(user, 'profile'):
                    if user.profile.user_type == 'customer':
                        user.profile.user_type = 'employee'
                        user.profile.department = 'other'
                        user.profile.requires_password_change = True
                        user.profile.save()
                        
                        # Grant basic quote permissions to new employees
                        AppPermission.objects.update_or_create(
                            user=user,
                            app='quotes',
                            defaults={'permission_level': 'view'}
                        )
                        
                        create_notification(
                            user=user,
                            title="Account Converted to Employee",
                            message="Your account has been converted to an employee account. You now have access to the quote system. Please change your password on next login.",
                            notification_type="info"
                        )
                        count += 1
        
        self.message_user(request, f'{count} users converted to employees with quote access.')
    
    # NEW: Quote-specific admin actions
    @admin.action(description='Assign Quote permissions to selected users')
    def assign_quote_permissions(self, request, queryset):
        count = 0
        employee_users = queryset.filter(
            profile__user_type__in=['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin']
        )
        
        with transaction.atomic():
            for user in employee_users:
                # Determine appropriate permission level based on user type
                if user.profile.user_type in ['sales_manager', 'blitzhub_admin']:
                    permission_level = 'admin'
                elif user.profile.user_type == 'sales_rep':
                    permission_level = 'edit'
                else:
                    permission_level = 'view'
                
                # Assign quote permissions
                AppPermission.objects.update_or_create(
                    user=user,
                    app='quotes',
                    defaults={'permission_level': permission_level}
                )
                
                # Also assign financial permissions for sales roles
                if user.profile.user_type in ['sales_rep', 'sales_manager']:
                    financial_level = 'edit' if user.profile.user_type == 'sales_manager' else 'view'
                    AppPermission.objects.update_or_create(
                        user=user,
                        app='financial',
                        defaults={'permission_level': financial_level}
                    )
                
                invalidate_permission_cache(user.id)
                count += 1
        
        create_bulk_notifications(
            users=employee_users,
            title="Quote System Access Granted",
            message="You have been granted access to the Quote Management system. You can now create and manage quotes for clients.",
            notification_type="success"
        )
        
        self.message_user(request, f'Quote permissions assigned to {count} users.')
    
    @admin.action(description='Assign Sales Representative role to selected users')
    def assign_sales_rep_role(self, request, queryset):
        count = 0
        with transaction.atomic():
            for user in queryset:
                if hasattr(user, 'profile'):
                    old_type = user.profile.user_type
                    user.profile.user_type = 'sales_rep'
                    user.profile.department = 'sales'
                    user.profile.save()
                    
                    # Assign appropriate permissions for sales rep
                    permissions = {
                        'quotes': 'edit',
                        'crm': 'edit',
                        'financial': 'view',
                        'reports': 'view'
                    }
                    
                    for app, level in permissions.items():
                        AppPermission.objects.update_or_create(
                            user=user,
                            app=app,
                            defaults={'permission_level': level}
                        )
                    
                    invalidate_permission_cache(user.id)
                    
                    create_notification(
                        user=user,
                        title="Role Updated to Sales Representative",
                        message="Your role has been updated to Sales Representative. You can now create and manage quotes, access CRM data, and view financial reports.",
                        notification_type="success"
                    )
                    count += 1
        
        self.message_user(request, f'{count} users assigned Sales Representative role.')
    
    @admin.action(description='Assign Sales Manager role to selected users')
    def assign_sales_manager_role(self, request, queryset):
        count = 0
        with transaction.atomic():
            for user in queryset:
                if hasattr(user, 'profile'):
                    old_type = user.profile.user_type
                    user.profile.user_type = 'sales_manager'
                    user.profile.department = 'sales'
                    user.profile.save()
                    
                    # Assign comprehensive permissions for sales manager
                    permissions = {
                        'quotes': 'admin',
                        'crm': 'admin',
                        'financial': 'edit',
                        'reports': 'admin',
                        'inventory': 'view'
                    }
                    
                    for app, level in permissions.items():
                        AppPermission.objects.update_or_create(
                            user=user,
                            app=app,
                            defaults={'permission_level': level}
                        )
                    
                    invalidate_permission_cache(user.id)
                    
                    create_notification(
                        user=user,
                        title="Role Updated to Sales Manager",
                        message="Your role has been updated to Sales Manager. You now have full access to quote management, CRM administration, and can approve high-value quotes.",
                        notification_type="success"
                    )
                    count += 1
        
        self.message_user(request, f'{count} users assigned Sales Manager role.')
    
    # Keep all your existing actions (assign_crm_permissions, etc.)
    @admin.action(description='Assign CRM permissions to selected employees')
    def assign_crm_permissions(self, request, queryset):
        count = 0
        employee_users = queryset.filter(profile__user_type__in=['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin'])
        
        with transaction.atomic():
            for user in employee_users:
                permission, created = AppPermission.objects.update_or_create(
                    user=user,
                    app='crm',
                    defaults={'permission_level': 'view'}
                )
                invalidate_permission_cache(user.id)
                count += 1
        
        create_bulk_notifications(
            users=employee_users,
            title="CRM Access Granted",
            message="You have been granted access to the CRM system.",
            notification_type="success"
        )
        
        self.message_user(request, f'CRM permissions assigned to {count} employees.')
    
    @admin.action(description='Assign Inventory permissions to selected employees')
    def assign_inventory_permissions(self, request, queryset):
        count = 0
        employee_users = queryset.filter(profile__user_type__in=['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin'])
        
        with transaction.atomic():
            for user in employee_users:
                permission, created = AppPermission.objects.update_or_create(
                    user=user,
                    app='inventory',
                    defaults={'permission_level': 'view'}
                )
                invalidate_permission_cache(user.id)
                count += 1
        
        create_bulk_notifications(
            users=employee_users,
            title="Inventory Access Granted", 
            message="You have been granted access to the Inventory Management system.",
            notification_type="success"
        )
        
        self.message_user(request, f'Inventory permissions assigned to {count} employees.')
    
    # Keep all your other existing actions...
    @admin.action(description='Force password reset for selected users')
    def reset_passwords(self, request, queryset):
        count = 0
        with transaction.atomic():
            for user in queryset:
                if hasattr(user, 'profile'):
                    user.profile.requires_password_change = True
                    user.profile.save()
                    
                    create_notification(
                        user=user,
                        title="Password Reset Required",
                        message="Your password must be changed on your next login for security reasons.",
                        notification_type="warning"
                    )
                    count += 1
        
        self.message_user(request, f'{count} users will be required to change passwords.')
    
    @admin.action(description='Unlock selected user accounts')
    def unlock_accounts(self, request, queryset):
        count = 0
        with transaction.atomic():
            for user in queryset:
                if hasattr(user, 'profile') and user.profile.is_account_locked:
                    user.profile.unlock_account()
                    
                    create_notification(
                        user=user,
                        title="Account Unlocked",
                        message="Your account has been unlocked by an administrator.",
                        notification_type="success"
                    )
                    count += 1
        
        self.message_user(request, f'{count} accounts unlocked successfully.')
    
    @admin.action(description='Send notification to selected users')
    def send_bulk_notification(self, request, queryset):
        create_bulk_notifications(
            users=queryset,
            title="Important Notice",
            message="This is a notification from the system administrator.",
            notification_type="info"
        )
        
        self.message_user(request, f'Notification sent to {queryset.count()} users.')

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# Enhanced AppPermission Admin with Quote Context
@admin.register(AppPermission)
class AppPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_user_type', 'app', 'permission_level', 'created_at', 'get_quote_activity')
    list_filter = (
        'app', 
        'permission_level', 
        'user__profile__user_type',
        'user__profile__department',
        'created_at'
    )
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    
    actions = [
        'bulk_assign_view_permission', 
        'bulk_assign_edit_permission',
        'bulk_assign_quote_permissions',  # NEW
        'bulk_revoke_permissions'         # NEW
    ]
    
    def get_user_type(self, obj):
        return obj.user.profile.get_user_type_display() if hasattr(obj.user, 'profile') else '-'
    get_user_type.short_description = 'User Type'
    
    # NEW: Show quote activity for users with quote permissions
    def get_quote_activity(self, obj):
        if obj.app == 'quotes' and hasattr(obj.user, 'created_quotes'):
            quote_count = obj.user.created_quotes.count()
            if quote_count > 0:
                recent_count = obj.user.created_quotes.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count()
                return format_html(
                    '<div title="Total: {} | Last 30 days: {}">'
                    '<strong>{}</strong> total<br/>'
                    '<small>{} recent</small>'
                    '</div>',
                    quote_count, recent_count, quote_count, recent_count
                )
            return format_html('<small>No quotes</small>')
        return '-'
    get_quote_activity.short_description = 'Quote Activity'
    
    @admin.action(description='Set permission level to View for selected')
    def bulk_assign_view_permission(self, request, queryset):
        count = queryset.update(permission_level='view')
        for permission in queryset:
            invalidate_permission_cache(permission.user.id)
        self.message_user(request, f'{count} permissions updated to View level.')
    
    @admin.action(description='Set permission level to Edit for selected')
    def bulk_assign_edit_permission(self, request, queryset):
        count = queryset.update(permission_level='edit')
        for permission in queryset:
            invalidate_permission_cache(permission.user.id)
        self.message_user(request, f'{count} permissions updated to Edit level.')
    
    # NEW: Bulk quote permissions assignment
    @admin.action(description='Assign comprehensive quote permissions to selected users')
    def bulk_assign_quote_permissions(self, request, queryset):
        count = 0
        with transaction.atomic():
            for permission in queryset.select_related('user__profile'):
                user = permission.user
                user_type = user.profile.user_type if hasattr(user, 'profile') else 'employee'
                
                # Assign quote permissions based on user type
                if user_type in ['sales_manager', 'blitzhub_admin']:
                    apps_and_levels = [
                        ('quotes', 'admin'),
                        ('financial', 'edit'),
                        ('reports', 'admin')
                    ]
                elif user_type == 'sales_rep':
                    apps_and_levels = [
                        ('quotes', 'edit'),
                        ('financial', 'view'),
                        ('reports', 'view')
                    ]
                else:
                    apps_and_levels = [('quotes', 'view')]
                
                for app, level in apps_and_levels:
                    AppPermission.objects.update_or_create(
                        user=user,
                        app=app,
                        defaults={'permission_level': level}
                    )
                
                invalidate_permission_cache(user.id)
                count += 1
        
        self.message_user(request, f'Quote permissions assigned to {count} users.')

# Security Monitoring Admins
@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_user_type', 'login_datetime', 'ip_address', 'get_location')
    list_filter = ('login_datetime', 'user__profile__user_type')
    search_fields = ('user__username', 'ip_address', 'user_agent')
    readonly_fields = ('user', 'login_datetime', 'ip_address', 'user_agent')
    date_hierarchy = 'login_datetime'
    
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

# Enhanced Notification Admin with Quote Context
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_user_type', 'title', 'type', 'is_read', 'created_at', 'get_action_info')
    list_filter = (
        'type', 
        'is_read', 
        'created_at',
        'user__profile__user_type',
        'user__profile__department'
    )
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    autocomplete_fields = ['user']
    
    actions = [
        'mark_as_read', 
        'mark_as_unread', 
        'delete_old_notifications',
        'send_quote_reminder_notifications'  # NEW
    ]
    
    def get_user_type(self, obj):
        return obj.user.profile.get_user_type_display() if hasattr(obj.user, 'profile') else '-'
    get_user_type.short_description = 'User Type'
    
    # NEW: Show action information for interactive notifications
    def get_action_info(self, obj):
        if obj.action_url and obj.action_text:
            return format_html(
                '<a href="{}" target="_blank" class="button">{}</a>',
                obj.action_url,
                obj.action_text
            )
        return '-'
    get_action_info.short_description = 'Action'
    
    @admin.action(description='Mark selected notifications as read')
    def mark_as_read(self, request, queryset):
        count = queryset.update(is_read=True)
        self.message_user(request, f'{count} notifications marked as read.')
    
    @admin.action(description='Mark selected notifications as unread')
    def mark_as_unread(self, request, queryset):
        count = queryset.update(is_read=False)
        self.message_user(request, f'{count} notifications marked as unread.')
    
    @admin.action(description='Delete notifications older than 30 days')
    def delete_old_notifications(self, request, queryset):
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        old_notifications = queryset.filter(created_at__lt=cutoff_date)
        count = old_notifications.count()
        old_notifications.delete()
        self.message_user(request, f'{count} old notifications deleted.')
    
    # NEW: Quote-specific notification action
    @admin.action(description='Send quote reminder notifications to sales team')
    def send_quote_reminder_notifications(self, request, queryset):
        """Send reminders about pending quotes to sales team"""
        from django.contrib.auth.models import User
        
        try:
            # Get quotes that need follow-up
            from quotes.models import Quote
            quotes_needing_followup = Quote.objects.filter(
                status__in=['sent', 'viewed', 'under_review'],
                created_at__lte=timezone.now() - timezone.timedelta(days=3)
            )
            
            # Get sales team members
            sales_team = User.objects.filter(
                profile__user_type__in=['sales_rep', 'sales_manager'],
                is_active=True
            )
            
            count = 0
            for user in sales_team:
                user_quotes = quotes_needing_followup.filter(
                    Q(assigned_to=user) | Q(created_by=user)
                )
                
                if user_quotes.exists():
                    quote_list = ', '.join([q.quote_number for q in user_quotes[:5]])
                    if user_quotes.count() > 5:
                        quote_list += f' and {user_quotes.count() - 5} more'
                    
                    create_notification(
                        user=user,
                        title="Quotes Need Follow-up",
                        message=f"You have {user_quotes.count()} quotes that may need follow-up: {quote_list}",
                        notification_type="warning",
                        action_url="/quotes/list/?status=sent,viewed,under_review",
                        action_text="Review Quotes"
                    )
                    count += 1
            
            self.message_user(request, f'Follow-up reminders sent to {count} sales team members.')
            
        except ImportError:
            self.message_user(request, 'Quote system not available.', level=messages.ERROR)


# Enhanced System Settings Admin with Quote Categories
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
admin.site.site_header = "BlitzTech Electronics Administration"
admin.site.site_title = "BlitzTech Admin"
admin.site.index_title = "Welcome to BlitzTech Electronics Administration"