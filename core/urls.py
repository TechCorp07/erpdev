# core/urls.py - CLEANED with working functionality only

"""
Enhanced URL configuration with comprehensive quote system integration.

This URL configuration includes only implemented functionality. Future features
are commented out with clear notes about what needs to be implemented.
"""

from django.urls import path, include
from . import views

app_name = 'core'

urlpatterns = [
    # =====================================
    # AUTHENTICATION URLS (All implemented ✓)
    # =====================================
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    
    # =====================================
    # DASHBOARD AND PROFILE URLS (All implemented ✓)
    # =====================================
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('system-logs/', views.system_logs, name='system_logs'),
    path('system-reports/', views.system_reports, name='system_reports'),
    path('audit-log/', views.audit_log_view, name='audit_log'),
    
    # =====================================
    # EMPLOYEE MANAGEMENT URLS (All implemented ✓)
    # =====================================
    path('employees/', views.employee_list_view, name='employee_list'),
    path('employees/add/', views.add_employee_view, name='add_employee'),
    path('employees/edit/<int:employee_id>/', views.edit_employee_view, name='edit_employee'),
    path('employees/permissions/<int:user_id>/', views.manage_permissions_view, name='manage_permissions'),
    path('employees/unlock/<int:user_id>/', views.unlock_user_account, name='unlock_user_account'),
    path('employees/performance-report/', views.employee_performance_report_view, name='employee_performance_report'),
    path('employees/bulk-assign-permissions/', views.bulk_assign_permissions_view, name='bulk_assign_permissions'),

    # Sales team management (Currently implemented ✓)
    path('sales-team/', views.sales_team_dashboard, name='sales_team_dashboard'),
    
    # FUTURE: Advanced sales team features (requires implementation)
    # TODO: Implement sales performance tracking and territory management
    # path('sales-team/performance/', views.sales_performance_view, name='sales_performance'),
    # path('sales-team/assign-territories/', views.assign_sales_territories, name='assign_territories'),
    
    # =====================================
    # NOTIFICATION URLS (Implemented ✓)
    # =====================================
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/export/', views.export_notifications_view, name='export_notifications'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/details/<int:notification_id>/', views.get_notification_details, name='get_notification_details'),
    path('notifications/archive/<int:notification_id>/', views.archive_notification, name='archive_notification'),
    path('notifications/updates/', views.get_notification_updates, name='get_notification_updates'),

    # FUTURE: Advanced notification features (requires implementation)
    # TODO: Implement bulk notification operations and quote-specific reminders
    # path('notifications/quote-reminders/', views.send_quote_reminders, name='send_quote_reminders'),
    # path('notifications/followup-alerts/', views.create_followup_alerts, name='create_followup_alerts'),
    
    # =====================================
    # AJAX/API URLS (All implemented ✓)
    # =====================================
    path('api/check-username/', views.check_username_availability, name='check_username'),
    path('api/notifications/', views.get_user_notifications, name='get_notifications'),
    path('api/get-notification-count/', views.get_notification_count, name='get_notification_count'),
    
    # Enhanced dashboard APIs with quote integration (All implemented ✓)
    path('api/dashboard-stats/', views.get_dashboard_stats, name='get_dashboard_stats'),
    path('api/user-permissions/', views.get_user_permissions_api, name='get_user_permissions'),
    path('api/navigation-context/', views.get_navigation_context_api, name='get_navigation_context'),
    
    # Quote-related quick actions from core dashboard (All implemented ✓)
    path('api/quick-quote-stats/', views.get_quick_quote_stats, name='get_quick_quote_stats'),
    path('api/recent-quotes/', views.get_recent_quotes_api, name='get_recent_quotes'),
    path('api/quotes-needing-attention/', views.get_quotes_needing_attention, name='get_quotes_needing_attention'),
    
    # =====================================
    # INTEGRATION ENDPOINTS (Implemented ✓)
    # =====================================
    # These endpoints help other apps integrate with core functionality
    
    # Quote system integration endpoints (All implemented ✓)
    path('integration/quote-user-access/', views.quote_user_access_check, name='quote_user_access_check'),
    path('integration/sales-team-lookup/', views.sales_team_lookup_api, name='sales_team_lookup'),
    path('integration/notify-quote-team/', views.notify_quote_team_api, name='notify_quote_team'),
    
    # =====================================
    # FUTURE FEATURES - COMMENTED OUT
    # =====================================
    # These URLs are for future implementation. Uncomment and implement views as needed.
    
    # SYSTEM ADMINISTRATION (requires implementation)
    # TODO: Create system settings management interface
    # TODO: Implement comprehensive user role management
    # TODO: Build permissions overview dashboard
    # path('admin/system-settings/', views.system_settings_view, name='system_settings'),
    # path('admin/user-roles/', views.manage_user_roles_view, name='manage_user_roles'),
    path('admin/permissions-overview/', views.permissions_overview_view, name='permissions_overview'),
    path('settings/notifications/', views.notification_settings_view, name='notification_settings'),
    path('settings/update-user-preference/', views.update_user_preference, name='update_user_preference'),
    path('settings/privacy/', views.privacy_settings_view, name='privacy_settings'),
    path('export/data/', views.export_data_view, name='export_data'),
    
    # QUOTE SYSTEM ADMINISTRATION (requires implementation)
    # TODO: Create quote system configuration interface
    # TODO: Implement quote template management
    # TODO: Build sales territory management system
    # path('admin/quote-settings/', views.quote_system_settings, name='quote_system_settings'),
    # path('admin/quote-templates/', views.manage_quote_templates, name='manage_quote_templates'),
    # path('admin/sales-territories/', views.manage_sales_territories, name='manage_sales_territories'),
    
    # REPORTING AND ANALYTICS (requires implementation)
    # TODO: Create comprehensive reporting dashboard
    # TODO: Implement user activity tracking and reporting
    # TODO: Build system usage analytics
    # TODO: Create sales performance reporting
    # TODO: Implement quote analytics and insights
    # TODO: Build team productivity metrics
    # path('reports/', views.reports_dashboard, name='reports_dashboard'),
    # path('reports/user-activity/', views.user_activity_report, name='user_activity_report'),
    # path('reports/system-usage/', views.system_usage_report, name='system_usage_report'),
    # path('reports/sales-performance/', views.sales_performance_report, name='sales_performance_report'),
    # path('reports/quote-analytics/', views.quote_analytics_report, name='quote_analytics_report'),
    # path('reports/team-productivity/', views.team_productivity_report, name='team_productivity_report'),
    
    # ADVANCED INTEGRATION ENDPOINTS (requires implementation)
    # TODO: Create user lookup API for external integrations
    # TODO: Implement permission checking API for third-party apps
    # TODO: Build notification creation API for external systems
    # path('integration/user-lookup/', views.user_lookup_api, name='user_lookup'),
    # path('integration/permission-check/', views.permission_check_api, name='permission_check'),
    # path('integration/create-notification/', views.create_notification_api, name='create_notification_api'),
]

# =====================================
# IMPLEMENTATION NOTES FOR FUTURE FEATURES
# =====================================

"""
PRIORITY 1 - Core Business Features:
1. system_settings_view: Admin interface for system configuration
2. reports_dashboard: Main reporting hub for business insights
3. sales_performance_report: Track sales team performance metrics

PRIORITY 2 - Enhanced User Management:
1. manage_user_roles_view: Bulk user role management interface
2. permissions_overview_view: Visual permissions management dashboard
3. user_activity_report: Monitor user engagement and system usage

PRIORITY 3 - Quote System Enhancements:
1. quote_system_settings: Configure quote defaults and business rules
2. manage_quote_templates: Create reusable quote templates
3. quote_analytics_report: Deep dive into quote performance

PRIORITY 4 - Advanced Features:
1. manage_sales_territories: Geographic and account-based territory management
2. team_productivity_report: Comprehensive team performance analytics
3. External API endpoints for third-party integrations

Each commented-out URL will need:
- Corresponding view function in views.py
- Template file in templates/core/
- Appropriate permission decorators
- Error handling and logging
- Unit tests
"""
