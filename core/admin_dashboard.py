# core/admin_dashboard.py
from django.contrib.admin import AdminSite
from django.urls import path
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import UserProfile, ApprovalRequest, SecurityEvent


class BlitzTechAdminSite(AdminSite):
    """
    Custom admin site for BlitzTech Electronics
    """
    site_header = 'BlitzTech Electronics Administration'
    site_title = 'BlitzTech Admin'
    index_title = 'System Administration Dashboard'
    
    @method_decorator(staff_member_required)
    def admin_dashboard_view(self, request):
        """
        Custom admin dashboard with key metrics
        """
        # Get date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # User statistics
        user_stats = {
            'total_users': UserProfile.objects.count(),
            'new_this_week': UserProfile.objects.filter(date_joined__gte=week_ago).count(),
            'new_this_month': UserProfile.objects.filter(date_joined__gte=month_ago).count(),
            'customers': UserProfile.objects.filter(user_type='customer').count(),
            'bloggers': UserProfile.objects.filter(user_type='blogger').count(),
            'employees': UserProfile.objects.filter(
                user_type__in=['employee', 'sales_rep', 'sales_manager']
            ).count(),
            'incomplete_profiles': UserProfile.objects.filter(profile_completed=False).count(),
            'social_accounts': UserProfile.objects.filter(is_social_account=True).count(),
        }
        
        # Approval statistics
        approval_stats = {
            'pending_requests': ApprovalRequest.objects.filter(status='pending').count(),
            'approved_this_week': ApprovalRequest.objects.filter(
                status='approved', reviewed_at__gte=week_ago
            ).count(),
            'rejected_this_week': ApprovalRequest.objects.filter(
                status='rejected', reviewed_at__gte=week_ago
            ).count(),
        }
        
        # Security statistics
        security_stats = {
            'failed_logins_today': SecurityEvent.objects.filter(
                event_type='login_failure',
                timestamp__date=today
            ).count(),
            'suspicious_activity': SecurityEvent.objects.filter(
                event_type='suspicious_activity',
                timestamp__gte=week_ago
            ).count(),
            'password_changes': SecurityEvent.objects.filter(
                event_type='password_change',
                timestamp__gte=week_ago
            ).count(),
        }
        
        # Recent activity
        recent_users = UserProfile.objects.select_related('user').order_by('-date_joined')[:5]
        pending_approvals = ApprovalRequest.objects.filter(
            status='pending'
        ).select_related('user').order_by('requested_at')[:5]
        
        context = {
            'title': 'Dashboard',
            'user_stats': user_stats,
            'approval_stats': approval_stats,
            'security_stats': security_stats,
            'recent_users': recent_users,
            'pending_approvals': pending_approvals,
        }
        
        return TemplateResponse(request, 'admin/dashboard.html', context)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_dashboard_view, name='admin_dashboard'),
        ]
        return custom_urls + urls

# Initialize custom admin site
blitztech_admin = BlitzTechAdminSite(name='blitztech_admin')