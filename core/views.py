from datetime import datetime, timedelta
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.views.decorators.http import require_http_methods
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.db import models
from django.db.models import Q, Count, Sum
from decimal import Decimal
from django.core.paginator import Paginator
import logging
import csv
import json

from .forms import (
    CoreLoginForm, UserRegistrationForm, UserProfileForm, 
    PasswordChangeCustomForm, EmployeeRegistrationForm, AppPermissionForm,
    ProfileCompletionForm, ApprovalRequestForm, AdminApprovalForm, 
)
from .models import UserProfile, AppPermission, LoginActivity, Notification, AuditLog, SecurityLog, ApprovalRequest, SecurityEvent
from .decorators import user_type_required, ajax_required, password_expiration_check
from .utils import (
    authenticate_user, can_user_manage_roles, create_bulk_notifications, get_recent_notifications, 
    get_unread_notifications_count, get_user_dashboard_stats, get_user_permissions, get_user_roles, has_app_permission,
    invalidate_permission_cache, create_notification, get_quote_dashboard_stats, get_navigation_context, log_security_event
)

logger = logging.getLogger('core.authentication')

# =====================================
# AUTHENTICATION VIEWS
# =====================================

def is_manager_or_admin(user):
    return (user.is_superuser or user.is_staff or
            (hasattr(user, 'profile') and 
             ((user.profile.department in ['admin', 'sales'] and user.profile.user_type == 'employee') or
              user.profile.department == 'admin')))

def is_admin_user(user):
    """Check if user has admin privileges"""
    return (user.is_superuser or user.is_staff or
            (hasattr(user, 'profile') and 
             user.profile.department == 'admin' and 
             user.profile.user_type == 'employee'))

def is_manager_user(user):
    """Check if user has manager privileges"""
    return (user.is_superuser or user.is_staff or
            (hasattr(user, 'profile') and 
             user.profile.department in ['admin', 'sales'] and 
             user.profile.user_type == 'employee'))

class CustomLoginView(LoginView):
    """Custom login view using CoreLoginForm with enhanced security"""
    form_class = CoreLoginForm
    template_name = 'core/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add context for different login types
        context['login_type'] = self.request.GET.get('type', 'customer')
        return context
    
    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')
        
        # Use custom authentication with rate limiting
        user = authenticate_user(self.request, username, password, remember_me)
        
        if user is None:
            # Authentication failed
            form.add_error(None, "Invalid username or password.")
            return self.form_invalid(form)
        
        # Check if account is locked
        if hasattr(user, 'profile') and user.profile.is_account_locked:
            locked_until = user.profile.account_locked_until
            locked_for = locked_until - timezone.now()
            minutes = round(locked_for.total_seconds() / 60)
            
            form.add_error(None, f"Your account is temporarily locked. Try again in {minutes} minutes.")
            return self.form_invalid(form)
        
        # Check if user must change password
        if hasattr(user, 'profile') and user.profile.requires_password_change:
            # Force password change at next login
            messages.warning(self.request, "You must change your password to continue.")
            return redirect('core:password_change')
        
        # Reset failed login counter
        if hasattr(user, 'profile'):
            user.profile.failed_login_count = 0
            user.profile.save(update_fields=['failed_login_count'])
            
        logger.info(f"User {username} logged in successfully")
        messages.success(self.request, f"Welcome back, {user.first_name or username}!")
        
        return super().form_valid(form)
    
    def form_invalid(self, form):
        username = form.cleaned_data.get('username', '')
        logger.warning(f"Failed login attempt for username: {username}")
        
        # Increment failed login counter for user if they exist
        if username:
            try:
                user = User.objects.get(username=username)
                if hasattr(user, 'profile'):
                    profile = user.profile
                    profile.failed_login_count += 1
                    
                    # Lock account after too many attempts
                    if profile.failed_login_count >= 5:
                        profile.lock_account(minutes=30)  # Use the method we added
                        logger.warning(f"Account locked for user {username} due to too many failed attempts")
                    else:
                        profile.save(update_fields=['failed_login_count'])
            except User.DoesNotExist:
                pass
        
        return super().form_invalid(form)

    def get_success_url(self):
        """Redirect based on user type and next parameter"""
        next_url = self.request.GET.get('next')
        
        # If there's a specific next URL, use it
        if next_url:
            return next_url
            
        user = self.request.user
        
        # Redirect based on user type
        if hasattr(user, 'profile'):
            user_type = user.profile.user_type
            
            if user_type in ['employee', 'blitzhub_admin', 'it_admin']:
                return reverse_lazy('core:dashboard')
            elif user_type == 'blogger':
                # Redirect to blog management when implemented
                return reverse_lazy('core:dashboard')  # For now
            else:  # customer or other
                return reverse_lazy('website:home')
        
        return reverse_lazy('website:home')

@require_http_methods(["GET", "POST"])
def logout_view(request):
    """Custom logout view with proper cleanup - supports both GET and POST"""
    if request.user.is_authenticated:
        username = request.user.username
        ip_address = request.META.get('REMOTE_ADDR', 'unknown')
        
        # Log security event with correct parameters
        log_security_event(
            user=request.user,
            event_type='login_success',  # There's no logout event type in the model
            description=f'User {username} logged out',
            ip_address=ip_address,
            details={'action': 'logout', 'username': username}
        )
        
        # Perform logout
        logout(request)
        logger.info(f"User {username} logged out")
        messages.success(request, "You have been successfully logged out.")
    
    # Redirect to home page
    return redirect('website:home')

def register_view(request):
    """User registration view for customers and bloggers"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Log the user in automatically
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Create welcome notification
            create_notification(
                user=user,
                title="Welcome to BlitzTech Electronics!",
                message="Your account has been created successfully. You can now access our services.",
                notification_type="success"
            )
            
            logger.info(f"New user registered: {user.username}")
            messages.success(request, f"Welcome to BlitzTech Electronics, {user.first_name}!")
            
            # Redirect based on intended use
            intended_use = request.GET.get('for', 'shopping')
            if intended_use == 'blog':
                return redirect('website:blog')
            else:
                return redirect('website:home')
    else:
        form = UserRegistrationForm()
    
    context = {
        'form': form,
        'registration_type': request.GET.get('for', 'general')
    }
    return render(request, 'core/register.html', context)

# =====================================
# USER MANAGEMENT VIEWS
# =====================================

@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.user_type in ['blitzhub_admin', 'it_admin']))
def user_management_view(request):
    """Enhanced user management view"""
    # Get filter parameters
    user_type_filter = request.GET.get('type', '')
    approval_status = request.GET.get('approval', '')
    search_query = request.GET.get('search', '')
    
    # Build queryset
    queryset = User.objects.select_related('profile').all()
    
    if user_type_filter:
        queryset = queryset.filter(profile__user_type=user_type_filter)
    
    if approval_status == 'approved':
        queryset = queryset.filter(profile__is_approved=True)
    elif approval_status == 'pending':
        queryset = queryset.filter(profile__is_approved=False)
    
    if search_query:
        queryset = queryset.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    queryset = queryset.order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page = request.GET.get('page')
    users = paginator.get_page(page)
    
    # Get statistics
    stats = {
        'total_users': User.objects.count(),
        'customers': UserProfile.objects.filter(user_type='customer').count(),
        'bloggers': UserProfile.objects.filter(user_type='blogger').count(),
        'employees': UserProfile.objects.filter(user_type__in=['employee', 'sales_rep', 'sales_manager']).count(),
        'pending_approval': UserProfile.objects.filter(is_approved=False).count(),
        'social_accounts': UserProfile.objects.filter(is_social_account=True).count(),
    }
    
    context = {
        'users': users,
        'stats': stats,
        'user_type_filter': user_type_filter,
        'approval_status': approval_status,
        'search_query': search_query,
        'user_types': UserProfile.USER_TYPES,
    }
    
    return render(request, 'core/user_management.html', context)

@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.user_type in ['blitzhub_admin', 'it_admin']))
def user_detail_view(request, user_id):
    """Detailed view of a specific user"""
    target_user = get_object_or_404(User, id=user_id)
    profile = target_user.profile
    
    # Get user's approval requests
    approval_requests = ApprovalRequest.objects.filter(user=target_user).order_by('-requested_at')
    
    # Get user's login activity
    login_activities = target_user.login_activities.all()[:10]
    
    # Get security events
    security_events = target_user.security_events.all()[:10]
    
    context = {
        'target_user': target_user,
        'profile': profile,
        'approval_requests': approval_requests,
        'login_activities': login_activities,
        'security_events': security_events,
    }
    
    return render(request, 'core/user_detail.html', context)

# =====================================
# APPROVAL REQUEST VIEWS
# =====================================

@login_required
def request_approval_view(request):
    """Allow users to request additional access"""
    user = request.user
    profile = user.profile
    
    # Employees don't need to request approval
    if profile.user_type == 'employee':
        messages.info(request, "Employees don't need to request additional access.")
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = ApprovalRequestForm(request.POST, user=user)
        if form.is_valid():
            approval_request = form.save(commit=False)
            approval_request.user = user
            approval_request.save()
            
            # Notify admins about new approval request
            admin_users = User.objects.filter(
                Q(is_superuser=True) | 
                Q(profile__user_type__in=['blitzhub_admin', 'it_admin'])
            )
            
            for admin in admin_users:
                create_notification(
                    user=admin,
                    title=f"New Approval Request: {approval_request.get_request_type_display()}",
                    message=f"{user.get_full_name()} has requested {approval_request.get_request_type_display()} access.",
                    notification_type='info',
                    action_url=reverse('core:manage_approvals')
                )
            
            messages.success(request, "Your approval request has been submitted and is being reviewed.")
            return redirect('core:customer_dashboard')
    else:
        form = ApprovalRequestForm(user=user)
    
    # Get existing requests
    existing_requests = ApprovalRequest.objects.filter(user=user).order_by('-requested_at')
    
    context = {
        'form': form,
        'existing_requests': existing_requests,
        'profile': profile,
    }
    
    return render(request, 'core/request_approval.html', context)

@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.user_type in ['blitzhub_admin', 'it_admin']))
def manage_approvals_view(request):
    """Admin view to manage approval requests"""
    # Get filter parameters
    status_filter = request.GET.get('status', 'pending')
    request_type_filter = request.GET.get('type', '')
    search_query = request.GET.get('search', '')
    
    # Build queryset
    queryset = ApprovalRequest.objects.all()
    
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    if request_type_filter:
        queryset = queryset.filter(request_type=request_type_filter)
    
    if search_query:
        queryset = queryset.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    queryset = queryset.order_by('-requested_at')
    
    # Pagination
    paginator = Paginator(queryset, 20)
    page = request.GET.get('page')
    approval_requests = paginator.get_page(page)
    
    # Get statistics
    stats = {
        'pending': ApprovalRequest.objects.filter(status='pending').count(),
        'approved': ApprovalRequest.objects.filter(status='approved').count(),
        'rejected': ApprovalRequest.objects.filter(status='rejected').count(),
    }
    
    context = {
        'approval_requests': approval_requests,
        'stats': stats,
        'status_filter': status_filter,
        'request_type_filter': request_type_filter,
        'search_query': search_query,
        'request_types': ApprovalRequest.REQUEST_TYPES,
    }
    
    return render(request, 'core/manage_approvals.html', context)

@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.user_type in ['blitzhub_admin', 'it_admin']))
def process_approval_view(request, request_id):
    """Process individual approval request"""
    approval_request = get_object_or_404(ApprovalRequest, id=request_id)
    
    if request.method == 'POST':
        form = AdminApprovalForm(request.POST, instance=approval_request)
        if form.is_valid():
            form.save(reviewer=request.user)
            
            action = form.cleaned_data['action']
            action_text = 'approved' if action == 'approve' else 'rejected'
            
            messages.success(request, f"Request {action_text} successfully!")
            
            # Log the action
            log_security_event(
                user=request.user,
                event_type=f'approval_{action}d',
                ip_address=request.META.get('REMOTE_ADDR'),
                details={
                    'target_user': approval_request.user.username,
                    'request_type': approval_request.request_type,
                    'action': action
                }
            )
            
            return redirect('core:manage_approvals')
    else:
        form = AdminApprovalForm(instance=approval_request)
    
    context = {
        'approval_request': approval_request,
        'form': form,
        'user_profile': approval_request.user.profile,
    }
    
    return render(request, 'core/process_approval.html', context)

# =====================================
# BULK APPROVAL VIEWS
# =====================================

@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.user_type in ['blitzhub_admin', 'it_admin']))
@require_http_methods(["POST"])
def bulk_approve_requests(request):
    """Bulk approve multiple requests"""
    request_ids = request.POST.getlist('request_ids')
    action = request.POST.get('action')  # 'approve' or 'reject'
    notes = request.POST.get('notes', '')
    
    if not request_ids:
        return JsonResponse({'success': False, 'error': 'No requests selected'})
    
    try:
        requests_qs = ApprovalRequest.objects.filter(id__in=request_ids, status='pending')
        processed_count = 0
        
        for approval_request in requests_qs:
            if action == 'approve':
                approval_request.approve(request.user, notes)
            else:
                approval_request.reject(request.user, notes)
            processed_count += 1
        
        # Log bulk action
        log_security_event(
            user=request.user,
            event_type=f'approval_{action}d',
            ip_address=request.META.get('REMOTE_ADDR'),
            details={
                'bulk_action': True,
                'count': processed_count,
                'action': action
            }
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'Successfully {action}d {processed_count} requests'
        })
        
    except Exception as e:
        logger.error(f"Bulk approval error: {str(e)}")
        return JsonResponse({'success': False, 'error': 'An error occurred processing the requests'})

# =====================================
# ENHANCED DASHBOARD WITH QUOTE INTEGRATION
# =====================================

@login_required
@password_expiration_check
def dashboard_view(request):
    """
    Enhanced dashboard view with role-based permissions.
    """
    user = request.user
    profile = user.profile
    
    # Check if user should be in customer dashboard instead
    if profile.user_type not in ['employee', 'sales_rep', 'sales_manager']:
        return redirect('core:customer_dashboard')
    
    # Check cache first to avoid expensive queries
    cache_key = f"dashboard_data:{user.id}"
    dashboard_context = cache.get(cache_key)
    
    if dashboard_context is None:
        # Use utility function to get user permissions properly
        user_permissions = get_user_permissions(user)
        
        # Cache permissions separately for longer period
        perm_cache_key = f"user_permissions:{user.id}"
        cache.set(perm_cache_key, user_permissions, 3600)  # Cache for 1 hour
        
        # Get dashboard context with optimized queries
        dashboard_context = {
            'user': user,
            'profile': profile,
            'app_permissions': user_permissions,
            'is_manager': has_app_permission(user, 'hr', 'view'),  # Updated function name
            'is_admin': user.is_superuser or profile.user_type in ['it_admin', 'general_manager'],
        }
        
        # Use single query for user statistics with aggregation
        if user_permissions:
            try:
                from django.db.models import Count
                
                # Get all counts in a single query
                stats_query = User.objects.aggregate(
                    total_users=Count('id'),
                    total_customers=Count('profile', filter=Q(profile__user_type='customer')),
                    total_bloggers=Count('profile', filter=Q(profile__user_type='blogger')),
                    total_employees=Count('profile', filter=Q(profile__user_type__in=['employee', 'sales_rep', 'sales_manager'])),
                    pending_approvals=Count('profile', filter=Q(profile__is_approved=False)),
                    social_users=Count('profile', filter=Q(profile__social_login=True)),
                )
                
                dashboard_context.update({
                    'stats': stats_query,
                    'has_crm_access': has_app_permission(user, 'crm'),
                    'has_quotes_access': has_app_permission(user, 'quotes'),
                    'has_inventory_access': has_app_permission(user, 'inventory'),
                    'has_admin_access': has_app_permission(user, 'admin'),
                })
                
            except Exception as e:
                logger.error(f"Error getting dashboard stats for user {user.username}: {e}")
                dashboard_context['stats'] = {}
        
        # Cache the dashboard context for 5 minutes
        cache.set(cache_key, dashboard_context, 300)
    
    # Get recent notifications (not cached for real-time updates)
    notifications = get_recent_notifications(user, limit=5)
    dashboard_context['notifications'] = notifications
    
    # Add navigation context
    nav_context = get_navigation_context(user)
    dashboard_context.update(nav_context)
    
    return render(request, 'core/dashboard.html', dashboard_context)

# =====================================
# ENHANCED PROFILE MANAGEMENT
# =====================================

@login_required
def profile_completion_view(request):
    """Complete user profile after registration or social login"""
    user = request.user
    profile = user.profile
    
    # Check if profile is already complete
    if profile.profile_completed:
        messages.info(request, "Your profile is already complete!")
        if profile.user_type == 'employee':
            return redirect('core:dashboard')
        else:
            return redirect('core:customer_dashboard')
    
    if request.method == 'POST':
        form = ProfileCompletionForm(request.POST, instance=profile, user=user)
        if form.is_valid():
            form.save()
            
            # Log profile completion
            log_security_event(
                user=user,
                event_type='profile_update',
                ip_address=request.META.get('REMOTE_ADDR'),
                details={'action': 'profile_completed'}
            )
            
            messages.success(request, "Profile completed successfully! You can now access approved features.")
            
            # Redirect based on user type
            if profile.user_type == 'employee':
                return redirect('core:dashboard')
            else:
                return redirect('core:customer_dashboard')
    else:
        form = ProfileCompletionForm(instance=profile, user=user)
    
    # Get incomplete fields and format them for display
    incomplete_fields_raw = profile.get_incomplete_fields()
    incomplete_fields = [field.replace('_', ' ').title() for field in incomplete_fields_raw]
    
    context = {
        'form': form,
        'profile': profile,
        'incomplete_fields': incomplete_fields,
        'user_type_display': profile.get_user_type_display(),
    }
    
    return render(request, 'core/profile_completion.html', context)

@login_required
def customer_dashboard_view(request):
    """Optimized dashboard for customers and bloggers"""
    user = request.user
    profile = user.profile
    
    # Check if user should be here
    if profile.user_type == 'employee':
        return redirect('core:dashboard')
    
    # Get user's approval requests in single query
    approval_requests = ApprovalRequest.objects.filter(
        user=user
    ).order_by('-requested_at')[:5]
    
    # Get recent notifications with single query
    notifications = user.notifications.filter(is_read=False)[:10]
    
    # Check access status
    access_status = {
        'shop': profile.can_access_shop(),
        'crm': profile.can_access_crm(),
        'blog': profile.can_access_blog() if profile.user_type == 'blogger' else False,
    }
    
    context = {
        'profile': profile,
        'approval_requests': approval_requests,
        'notifications': notifications,
        'access_status': access_status,
        'profile_completed': profile.profile_completed,
        'incomplete_fields': profile.get_incomplete_fields(),
    }
    
    return render(request, 'core/customer_dashboard.html', context)

@login_required
@password_expiration_check
def profile_view(request):
    """
    Enhanced user profile view that shows role-appropriate information
    including quote-related statistics for sales team members.
    """
    user = request.user
    profile = user.profile if hasattr(user, 'profile') else None
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=user)
        
        # Handle profile image removal
        if request.POST.get('remove_image') and profile and profile.profile_image:
            profile.profile_image.delete()
            profile.profile_image = None
            profile.save()
        
        if form.is_valid():
            form.save()
            
            create_notification(
                user=user,
                title="Profile Updated",
                message="Your profile information has been updated successfully.",
                notification_type="success"
            )
            # Log profile update
            log_security_event(
                user=user,
                event_type='profile_update',
                ip_address=request.META.get('REMOTE_ADDR'),
                details={'action': 'profile_edited'}
            )
            
            logger.info(f"Profile updated for user {user.username}")
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('core:profile')
    else:
        form = UserProfileForm(instance=profile, user=user)
    
        # Get user's recent activity
    recent_logins = user.login_activities.all()[:5]
    recent_approvals = user.approval_requests.all()[:5]
    
    # Enhanced context with role-specific information
    context = {
        'form': form,
        'user_profile': profile,
        'recent_logins': recent_logins,
        'recent_approvals': recent_approvals,
        'access_status': {
            'shop': profile.can_access_shop(),
            'crm': profile.can_access_crm(),
            'blog': profile.can_access_blog() if profile.user_type == 'blogger' else False,
        }
    }
    
    # Add quote statistics for sales team members
    if profile and profile.can_manage_quotes:
        try:
            from quotes.models import Quote
            
            # User's quote statistics
            user_quotes = Quote.objects.filter(
                Q(assigned_to=user) | Q(created_by=user)
            )
            
            context.update({
                'quote_statistics': {
                    'total_quotes': user_quotes.count(),
                    'active_quotes': user_quotes.filter(
                        status__in=['draft', 'sent', 'viewed', 'under_review']
                    ).count(),
                    'accepted_quotes': user_quotes.filter(status='accepted').count(),
                    'total_value': user_quotes.filter(
                        status__in=['accepted', 'converted']
                    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
                    'this_month_quotes': user_quotes.filter(
                        created_at__gte=timezone.now().replace(day=1)
                    ).count(),
                }
            })
        except ImportError:
            # Quote system not available
            pass
    
    return render(request, 'core/profile.html', context)

# =====================================
# ENHANCED EMPLOYEE MANAGEMENT
# =====================================

@user_passes_test(is_admin_user)
@password_expiration_check
def employee_list_view(request):
    """
    Enhanced employee list with quote performance metrics.
    """
    # Get all employee profiles with optimized queries
    employees = UserProfile.objects.filter(
        user_type='employee').select_related('user').annotate(
        quote_count=Count('user__created_quotes', distinct=True),
        total_quote_value=Sum('user__created_quotes__total_amount')
    )
    
    # Add optional filtering
    department = request.GET.get('department')
    user_type = request.GET.get('user_type')
    search = request.GET.get('search')
    
    if department:
        employees = employees.filter(department=department)
    
    if user_type:
        employees = employees.filter(user_type=user_type)
    
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__username__icontains=search)
        )
    
    # Calculate team performance metrics
    team_stats = {
        'total_employees': employees.count(),
        'sales_team_size': employees.filter(user_type__in=['sales_rep', 'sales_manager']).count(),
        'total_quotes_created': employees.aggregate(total=Sum('quote_count'))['total'] or 0,
        'total_quote_value': employees.aggregate(total=Sum('total_quote_value'))['total'] or Decimal('0.00'),
    }
    
    context = {
        'employees': employees,
        'team_stats': team_stats,
        'departments': UserProfile.DEPARTMENTS,
        'user_types': UserProfile.USER_TYPES,
        'current_filters': {
            'department': department,
            'user_type': user_type,
            'search': search,
        }
    }
    
    logger.info(f"Employee list viewed by {request.user.username}")
    return render(request, 'core/employee_list.html', context)

@user_passes_test(is_admin_user)
@password_expiration_check
def add_employee_view(request):
    """
    Enhanced employee creation with automatic permission setup.
    """
    if request.method == 'POST':
        form = EmployeeRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            
            # Set up default permissions based on user type using our utility function
            from .utils import setup_default_user_permissions
            setup_default_user_permissions(user)
            
            # Set temporary password change requirement
            user.profile.requires_password_change = True
            user.profile.save()
            
            # Create welcome notification with role-specific information
            if user.profile.user_type in ['sales_rep', 'sales_manager']:
                welcome_message = (
                    "Welcome to the BlitzTech Electronics sales team! Your account has been created "
                    "with access to quote management, CRM, and reporting systems. Please change your "
                    "password on first login."
                )
            else:
                welcome_message = (
                    "Welcome to BlitzTech Electronics! Your employee account has been created. "
                    "Please change your password on first login."
                )
            
            create_notification(
                user=user,
                title="Welcome to BlitzTech Electronics Team!",
                message=welcome_message,
                notification_type="info"
            )
            
            logger.info(f"New employee {user.username} created by {request.user.username}")
            messages.success(request, f'Employee {user.get_full_name()} has been added successfully with appropriate permissions.')
            return redirect('core:employee_list')
    else:
        form = EmployeeRegistrationForm()
    
    context = {'form': form}
    return render(request, 'core/add_employee.html', context)

@user_passes_test(is_admin_user)
@password_expiration_check
def edit_employee_view(request, employee_id):
    """Edit employee details (admin only)"""
    employee_profile = get_object_or_404(UserProfile, id=employee_id)
    employee_user = employee_profile.user
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=employee_profile, user=employee_user)
        
        if form.is_valid():
            form.save()
            
            # Create notification for employee
            create_notification(
                user=employee_user,
                title="Profile Updated by Administrator",
                message="Your profile information has been updated by an administrator.",
                notification_type="info"
            )
            
            logger.info(f"Employee {employee_user.username} updated by {request.user.username}")
            messages.success(request, f'Employee {employee_user.get_full_name()} has been updated successfully.')
            return redirect('core:employee_list')
    else:
        form = UserProfileForm(instance=employee_profile, user=employee_user)
    
    context = {
        'form': form,
        'employee': employee_user,
        'employee_profile': employee_profile,
    }
    return render(request, 'core/edit_employee.html', context)

# =====================================
# ENHANCED NOTIFICATION SYSTEM
# =====================================

@login_required
@password_expiration_check
def notifications_view(request):
    """
    Enhanced notifications view with filtering and quote-specific actions.
    """
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by notification type if requested
    filter_type = request.GET.get('type')
    if filter_type:
        notifications = notifications.filter(type=filter_type)
    
    # Pagination for large notification lists
    from django.core.paginator import Paginator
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get notification type statistics for filter interface
    type_stats = Notification.objects.filter(user=request.user).values('type').annotate(
        count=Count('id')
    ).order_by('type')
    
    context = {
        'page_obj': page_obj,
        'type_stats': type_stats,
        'current_filter': filter_type,
        'notification_types': Notification.NOTIFICATION_TYPES,
    }
    
    return render(request, 'core/notifications.html', context)

@ajax_required
@login_required
def mark_notification_read(request, notification_id):
    """
    Enhanced notification marking with cache invalidation.
    """
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        
        # Update notification cache
        cache_key = f"user_notifications:{request.user.id}"
        cache.delete(cache_key)  # Force recalculation next time
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}, status=400)

@ajax_required
@login_required
def get_notification_count(request):
    """
    AJAX endpoint to get current unread notification count for navbar updates.
    """
    count = get_unread_notifications_count(request.user)
    return JsonResponse({'count': count})

# =====================================
# ENHANCED PERMISSION MANAGEMENT
# =====================================

@login_required
@user_type_required(['admin', 'general_manager'])
@password_expiration_check
def manage_permissions_view(request, user_id):
    """
    Enhanced permission management with role-based system support.
    """
    target_user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Handle role assignment/updates
        with transaction.atomic():
            from .models import EmployeeRole, UserRole
            
            # Get selected roles from the form
            selected_role_ids = request.POST.getlist('roles')
            
            if selected_role_ids:
                # Remove existing active roles
                UserRole.objects.filter(user=target_user, is_active=True).update(is_active=False)
                
                # Add new roles
                for role_id in selected_role_ids:
                    try:
                        role = EmployeeRole.objects.get(id=role_id)
                        user_role, created = UserRole.objects.get_or_create(
                            user=target_user,
                            role=role,
                            defaults={
                                'assigned_by': request.user,
                                'is_active': True
                            }
                        )
                        if not created and not user_role.is_active:
                            user_role.is_active = True
                            user_role.assigned_by = request.user
                            user_role.assigned_at = timezone.now()
                            user_role.save()
                            
                        logger.info(
                            f"User {request.user.username} assigned role {role.name} "
                            f"to user {target_user.username}"
                        )
                    except EmployeeRole.DoesNotExist:
                        continue
            else:
                # Remove all roles if none selected
                UserRole.objects.filter(user=target_user, is_active=True).update(is_active=False)
            
            # Invalidate permissions cache for this user
            invalidate_permission_cache(target_user.id)
            
            # Create notification for target user
            active_roles = get_user_roles(target_user)
            if active_roles:
                role_list = ', '.join(active_roles)
                create_notification(
                    user=target_user,
                    title="Roles Updated",
                    message=f"Your roles have been updated: {role_list}",
                    notification_type="info"
                )
            else:
                create_notification(
                    user=target_user,
                    title="Roles Removed",
                    message="All your roles have been removed. Contact your administrator if this is incorrect.",
                    notification_type="warning"
                )
        
        messages.success(request, f'Roles for {target_user.username} have been updated.')
        return redirect('core:manage_permissions', user_id=user_id)
    
    # GET request - show the permission management form
    from .models import EmployeeRole
    
    # Get available roles and current user roles
    available_roles = EmployeeRole.objects.filter(is_active=True).order_by('hierarchy_level', 'name')
    current_roles = get_user_roles(target_user)
    current_permissions = get_user_permissions(target_user)
    
    # Get current active UserRole objects for form population
    current_user_roles = UserRole.objects.filter(
        user=target_user, 
        is_active=True
    ).select_related('role')
    
    context = {
        'target_user': target_user,
        'available_roles': available_roles,
        'current_roles': current_roles,
        'current_permissions': current_permissions,
        'current_user_roles': current_user_roles,
        'can_manage_roles': can_user_manage_roles(request.user),
    }
    
    return render(request, 'core/manage_permissions.html', context)

# =====================================
# PASSWORD MANAGEMENT
# =====================================

class CustomPasswordChangeView(PasswordChangeView):
    """Enhanced password change view with security features"""
    form_class = PasswordChangeCustomForm
    template_name = 'core/password_change.html'
    success_url = reverse_lazy('core:profile')
    
    def form_valid(self, form):
        user = self.request.user
        new_password = form.cleaned_data.get('new_password1')
        password_hash = make_password(new_password)
        
        # Check if password has been used before (if method exists)
        if hasattr(user, 'profile') and hasattr(user.profile, 'has_used_password_before'):
            if user.profile.has_used_password_before(password_hash):
                form.add_error('new_password1', "You cannot reuse a previous password.")
                return self.form_invalid(form)
        
        with transaction.atomic():
            # Change the password
            response = super().form_valid(form)
            
            # Update the session to prevent logging out
            update_session_auth_hash(self.request, self.request.user)
            
            # Record password change in profile
            if hasattr(user, 'profile'):
                user.profile.record_password_change(password_hash)
            
            # Create notification
            create_notification(
                user=user,
                title="Password Changed",
                message="Your password has been changed successfully.",
                notification_type="success"
            )
                
        logger.info(f"Password changed for user {user.username}")
        messages.success(self.request, 'Your password has been changed successfully.')
        return response

# =====================================
# UTILITY VIEWS
# =====================================

@user_type_required(['it_admin'])
def unlock_user_account(request, user_id):
    """Administrative action to unlock a user account"""
    user = get_object_or_404(User, id=user_id)
    if hasattr(user, 'profile'):
        user.profile.unlock_account()
        
        # Create notification for unlocked user
        create_notification(
            user=user,
            title="Account Unlocked",
            message="Your account has been unlocked by an administrator.",
            notification_type="success"
        )
        
        logger.info(f"Account unlocked for {user.username} by {request.user.username}")
        messages.success(request, f"Account for {user.username} has been unlocked.")
    
    return redirect('core:employee_list')

# =====================================
# API/AJAX VIEWS FOR FUTURE USE
# =====================================

@ajax_required
@login_required
def check_username_availability(request):
    """Check if username is available (for registration forms)"""
    username = request.GET.get('username', '')
    
    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Username too short'})
    
    exists = User.objects.filter(username=username).exists()
    
    return JsonResponse({
        'available': not exists,
        'message': 'Username available' if not exists else 'Username already taken'
    })

@ajax_required
@login_required
def get_user_notifications(request):
    """Get unread notifications for the navbar (AJAX)"""
    notifications = Notification.objects.filter(
        user=request.user, 
        is_read=False
    ).order_by('-created_at')[:5]
    
    notification_data = [{
        'id': notif.id,
        'title': notif.title,
        'message': notif.message[:100],
        'type': notif.type,
        'created_at': notif.created_at.strftime('%M d, %Y %H:%M'),
    } for notif in notifications]
    
    return JsonResponse({
        'notifications': notification_data,
        'count': len(notification_data)
    })

# =====================================
# API ENDPOINTS FOR DASHBOARD UPDATES
# =====================================

@ajax_required
@login_required
def get_dashboard_stats(request):
    """
    AJAX endpoint to get real-time dashboard statistics including quote metrics.
    """
    try:
        stats = {}
        user_permissions = get_user_permissions(request.user)
        
        # Quote statistics for users with quote access
        if user_permissions.get('quotes'):
            quote_stats = get_quote_dashboard_stats(request.user)
            stats['quotes'] = quote_stats
        
        # CRM statistics for users with CRM access
        if user_permissions.get('crm'):
            try:
                from crm.models import CustomerInteraction
                stats['crm'] = {
                    'pending_followups': CustomerInteraction.objects.filter(
                        next_followup__lte=timezone.now(),
                        is_completed=False
                    ).count()
                }
            except ImportError:
                pass
        
        # Notification count
        stats['notifications'] = {
            'unread_count': get_unread_notifications_count(request.user)
        }
        
        return JsonResponse({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats for user {request.user.username}: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@user_type_required(['sales_manager', 'blitzhub_admin', 'it_admin'])
@password_expiration_check
def sales_team_dashboard(request):

    """ Specialized dashboard for sales team management.
        Provides comprehensive overview of sales team performance and quote metrics.
    """
    
    if not has_app_permission(request.user, 'quotes', 'admin'):
        messages.error(request, 'You do not have permission to access sales team management.')
        return redirect('core:dashboard')
    
    try:
        from quotes.models import Quote
        from django.db.models import Q, Count, Sum, Avg
        
        # Get sales team members
        sales_team = User.objects.filter(
            profile__user_type__in=['sales_rep', 'sales_manager'],
            is_active=True
        ).select_related('profile').annotate(
            quote_count=Count('created_quotes'),
            total_value=Sum('created_quotes__total_amount'),
            avg_quote_value=Avg('created_quotes__total_amount'),
            accepted_quotes=Count('created_quotes', filter=Q(created_quotes__status='accepted'))
        )
        
        # Team performance metrics
        team_stats = {
            'total_members': sales_team.count(),
            'total_quotes': Quote.objects.count(),
            'total_value': Quote.objects.filter(
                status__in=['accepted', 'converted']
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
            'active_quotes': Quote.objects.filter(
                status__in=['draft', 'sent', 'viewed', 'under_review']
            ).count(),
        }
        
        context = {
            'sales_team': sales_team,
            'team_stats': team_stats,
        }
        
        return render(request, 'core/sales_team_dashboard.html', context)
        
    except ImportError:
        messages.error(request, 'Quote system is not available.')
        return redirect('core:dashboard')

@ajax_required
@login_required
def get_quick_quote_stats(request):

    # AJAX endpoint for quick quote statistics for dashboard widgets.

    if not has_app_permission(request.user, 'quotes', 'view'):
        return JsonResponse({'success': False, 'error': 'No quote access'})
    
    try:
        stats = get_quote_dashboard_stats(request.user)
        return JsonResponse({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error getting quick quote stats: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@ajax_required
@login_required
def get_recent_quotes_api(request):

    # AJAX endpoint to get recent quotes for dashboard display.

    if not has_app_permission(request.user, 'quotes', 'view'):
        return JsonResponse({'success': False, 'error': 'No quote access'})
    
    try:
        from quotes.models import Quote
        from django.db.models import Q
        
        # Build user filter
        if request.user.profile.is_admin:
            user_filter = Q()
        else:
            user_filter = Q(assigned_to=request.user) | Q(created_by=request.user)
        
        recent_quotes = Quote.objects.filter(user_filter).select_related(
            'client', 'assigned_to'
        ).order_by('-created_at')[:5]
        
        quotes_data = []
        for quote in recent_quotes:
            quotes_data.append({
                'id': quote.id,
                'quote_number': quote.quote_number,
                'client_name': quote.client.name,
                'title': quote.title,
                'status': quote.status,
                'status_display': quote.get_status_display(),
                'total_amount': float(quote.total_amount),
                'currency': quote.currency,
                'created_at': quote.created_at.strftime('%Y-%m-%d'),
                'url': reverse('quotes:quote_detail', args=[quote.id])
            })
        
        return JsonResponse({'success': True, 'quotes': quotes_data})
        
    except Exception as e:
        logger.error(f"Error getting recent quotes: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@ajax_required
@login_required
def get_quotes_needing_attention(request):

    # AJAX endpoint to get quotes that need user attention.

    if not has_app_permission(request.user, 'quotes', 'view'):
        return JsonResponse({'success': False, 'error': 'No quote access'})
    
    try:
        from quotes.models import Quote
        from django.db.models import Q
        
        # Build user filter
        if request.user.profile.is_admin:
            user_filter = Q()
        else:
            user_filter = Q(assigned_to=request.user) | Q(created_by=request.user)
        
        # Different criteria based on user role
        if request.user.profile.user_type in ['sales_manager', 'blitzhub_admin', 'it_admin']:
            # Managers see high-value drafts and old quotes
            attention_quotes = Quote.objects.filter(
                Q(status='draft', total_amount__gte=Decimal('10000.00')) |
                Q(status__in=['sent', 'viewed'], 
                  sent_date__lte=timezone.now() - timezone.timedelta(days=7))
            ).select_related('client', 'assigned_to')[:5]
        else:
            # Sales reps see their drafts and recent sends needing follow-up
            attention_quotes = Quote.objects.filter(
                user_filter,
                Q(status='draft') |
                Q(status__in=['sent', 'viewed'], 
                  sent_date__lte=timezone.now() - timezone.timedelta(days=3))
            ).select_related('client', 'assigned_to')[:5]
        
        quotes_data = []
        for quote in attention_quotes:
            reason = ''
            if quote.status == 'draft':
                if quote.total_amount >= Decimal('10000.00'):
                    reason = 'High-value draft requiring approval'
                else:
                    reason = 'Draft quote incomplete'
            elif quote.status in ['sent', 'viewed']:
                days_ago = (timezone.now() - quote.sent_date).days
                reason = f'Sent {days_ago} days ago - needs follow-up'
            
            quotes_data.append({
                'id': quote.id,
                'quote_number': quote.quote_number,
                'client_name': quote.client.name,
                'status': quote.status,
                'status_display': quote.get_status_display(),
                'total_amount': float(quote.total_amount),
                'reason': reason,
                'url': reverse('quotes:quote_detail', args=[quote.id])
            })
        
        return JsonResponse({'success': True, 'quotes': quotes_data})
        
    except Exception as e:
        logger.error(f"Error getting quotes needing attention: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@ajax_required
@login_required  
def get_user_permissions_api(request):

    # AJAX endpoint to get comprehensive user permissions.

    try:
        permissions = get_user_permissions(request.user)
        return JsonResponse({'success': True, 'permissions': permissions})
    except Exception as e:
        logger.error(f"Error getting user permissions: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@ajax_required
@login_required
def get_navigation_context_api(request):

    # AJAX endpoint to get navigation context for dynamic menu building.

    try:
        navigation = get_navigation_context(request.user)
        return JsonResponse({'success': True, 'navigation': navigation})
    except Exception as e:
        logger.error(f"Error getting navigation context: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

# Integration API endpoints for other apps

@ajax_required
@login_required
def quote_user_access_check(request):

    # API endpoint for other apps to check if a user has access to a specific quote.

    try:
        quote_id = request.GET.get('quote_id')
        if not quote_id:
            return JsonResponse({'success': False, 'error': 'quote_id required'})
        
        from quotes.models import Quote
        quote = Quote.objects.get(id=quote_id)
        
        has_access = (
            request.user.profile.is_admin or
            quote.created_by == request.user or
            quote.assigned_to == request.user
        )
        
        return JsonResponse({
            'success': True,
            'has_access': has_access,
            'quote_number': quote.quote_number,
            'status': quote.status
        })
        
    except Quote.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Quote not found'})
    except Exception as e:
        logger.error(f"Error checking quote access: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@ajax_required
@login_required
def sales_team_lookup_api(request):

    # API endpoint to get sales team members for assignment purposes.
    
    try:
        sales_team = User.objects.filter(
            profile__user_type__in=['sales_rep', 'sales_manager'],
            is_active=True
        ).select_related('profile').values(
            'id', 'username', 'first_name', 'last_name', 
            'profile__user_type', 'profile__department'
        )
        
        team_data = []
        for member in sales_team:
            team_data.append({
                'id': member['id'],
                'name': f"{member['first_name']} {member['last_name']}".strip() or member['username'],
                'username': member['username'],
                'role': member['profile__user_type'],
                'department': member['profile__department']
            })
        
        return JsonResponse({'success': True, 'team_members': team_data})
        
    except Exception as e:
        logger.error(f"Error getting sales team: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@ajax_required
def notify_quote_team_api(request):

    # API endpoint for sending notifications to quote team members.

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        
        user_ids = data.get('user_ids', [])
        title = data.get('title', '')
        message = data.get('message', '')
        quote_id = data.get('quote_id')
        
        if not all([user_ids, title, message]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})
        
        users = User.objects.filter(id__in=user_ids)
        
        action_url = None
        action_text = None
        if quote_id:
            action_url = reverse('quotes:quote_detail', args=[quote_id])
            action_text = 'View Quote'
        
        created_notifications = create_bulk_notifications(
            users=users,
            title=title,
            message=message,
            notification_type='quote',
            action_url=action_url,
            action_text=action_text
        )
        
        return JsonResponse({
            'success': True,
            'notifications_sent': len(created_notifications)
        })
        
    except Exception as e:
        logger.error(f"Error sending team notifications: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)  # or your preferred permission check
def system_logs(request):
    logs = SecurityLog.objects.order_by('-timestamp')[:100]
    return render(request, 'core/system_logs.html', {'logs': logs})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff)  # restrict as you need!
def system_reports(request):
    # Add your stats/data logic here!
    return render(request, 'core/system_reports.html', {})

# Only admins (BlitzHub Admins or IT Admins) can view this
@user_passes_test(is_admin_user)
def permissions_overview_view(request):
    """
    Shows a table of all users and their app permissions based on roles.
    """
    users = User.objects.filter(
        profile__user_type__in=['employee', 'sales_rep', 'sales_manager']
    ).select_related('profile').order_by('username')
    
    # Build a map: user_id -> list of permissions from roles
    permissions_map = {}
    
    for user in users:
        user_permissions = get_user_permissions(user)
        user_roles = get_user_roles(user)
        
        # Convert permissions dict to list of objects for template compatibility
        permission_objects = []
        for app, level in user_permissions.items():
            permission_objects.append({
                'app': app,
                'permission_level': level,
                'get_app_display': dict(AppPermission.APP_CHOICES).get(app, app),
                'get_permission_level_display': dict(AppPermission.PERMISSION_LEVELS).get(level, level)
            })
        
        permissions_map[user.id] = {
            'permissions': permission_objects,
            'roles': user_roles
        }

    context = {
        'users': users,
        'permissions_map': permissions_map,
    }
    return render(request, 'core/permissions_overview.html', context)

@user_passes_test(is_manager_user)
def employee_performance_report_view(request):
    # Get filter params from GET request
    department = request.GET.get('department')
    user_type = request.GET.get('user_type')
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    search = request.GET.get('search')
    sort = request.GET.get('sort', 'user__first_name')  # Default sort

    employees = UserProfile.objects.filter(user_type='employee')

    # Filtering
    if department:
        employees = employees.filter(department=department)
    if user_type:
        employees = employees.filter(user_type=user_type)
    if search:
        employees = employees.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )

    # Date filtering (if you track last_login or similar)
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, "%Y-%m-%d")
            employees = employees.filter(last_login__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, "%Y-%m-%d")
            employees = employees.filter(last_login__lte=date_to_parsed)
        except ValueError:
            pass

    # Sorting
    employees = employees.order_by(sort)

    # Gather department and user_type choices for filters
    DEPARTMENTS = UserProfile.DEPARTMENTS
    USER_TYPES = [ut for ut in UserProfile.USER_TYPES if ut[0] != 'customer']

    context = {
        'employees': employees,
        'departments': DEPARTMENTS,
        'user_types': USER_TYPES,
        'request': request,  # For access in template
    }
    
    if 'export' in request.GET:
        # Export as CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="employee_performance_report.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Department', 'Role', 'Email', 'Last Login',
            'Quotes Created', 'Total Quote Value', 'Conversion Rate', 'Avg Logins/Week'
        ])
        for emp in employees:
            writer.writerow([
                emp.user.get_full_name() if emp.user else '',
                emp.get_department_display(),
                emp.get_user_type_display(),
                emp.user.email if emp.user else '',
                emp.last_login.strftime('%Y-%m-%d %H:%M') if emp.last_login else '',
                getattr(emp, 'quote_count', 'N/A'),
                getattr(emp, 'total_quote_value', 'N/A'),
                f"{getattr(emp, 'conversion_rate', 0):.1f}%" if getattr(emp, 'conversion_rate', None) is not None else 'N/A',
                getattr(emp, 'avg_login_frequency', 'N/A'),
            ])
        return response
    
    return render(request, 'core/employee_performance_report.html', context)

@csrf_exempt
@user_passes_test(is_manager_user)
def bulk_assign_permissions_view(request):
    """
    Assign roles to multiple users at once (AJAX endpoint).
    Expects POST data: { user_ids: [id,...], role_id: 123, action: 'assign'/'remove' }
    """
    if request.method != "POST":
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body.decode())
        user_ids = data.get('user_ids', [])
        role_id = data.get('role_id')
        action = data.get('action', 'assign')  # 'assign' or 'remove'

        if not user_ids or not role_id:
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        from django.contrib.auth.models import User
        from .models import EmployeeRole, UserRole

        try:
            role = EmployeeRole.objects.get(pk=role_id, is_active=True)
        except EmployeeRole.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid role'}, status=400)

        updated_users = []
        
        with transaction.atomic():
            for uid in user_ids:
                try:
                    user = User.objects.get(pk=uid)
                    
                    if action == 'assign':
                        # Assign role to user
                        user_role, created = UserRole.objects.get_or_create(
                            user=user,
                            role=role,
                            defaults={
                                'assigned_by': request.user,
                                'is_active': True
                            }
                        )
                        if not created and not user_role.is_active:
                            user_role.is_active = True
                            user_role.assigned_by = request.user
                            user_role.assigned_at = timezone.now()
                            user_role.save()
                        
                        updated_users.append(user.username)
                        
                        # Create notification
                        create_notification(
                            user=user,
                            title="New Role Assigned",
                            message=f"You have been assigned the role: {role.display_name}",
                            notification_type="info"
                        )
                        
                    elif action == 'remove':
                        # Remove role from user
                        updated_count = UserRole.objects.filter(
                            user=user,
                            role=role,
                            is_active=True
                        ).update(is_active=False)
                        
                        if updated_count > 0:
                            updated_users.append(user.username)
                            
                            # Create notification
                            create_notification(
                                user=user,
                                title="Role Removed",
                                message=f"The role '{role.display_name}' has been removed from your account.",
                                notification_type="warning"
                            )
                    
                    # Invalidate user's permission cache
                    invalidate_permission_cache(user.id)
                    
                except User.DoesNotExist:
                    continue

        action_past = 'assigned' if action == 'assign' else 'removed'
        message = f"Role '{role.display_name}' {action_past} for {len(updated_users)} users"
        
        logger.info(f"Bulk role {action}: {message} by {request.user.username}")
        
        return JsonResponse({
            'success': True, 
            'message': message,
            'updated_users': updated_users
        })
        
    except Exception as e:
        logger.error(f"Error in bulk_assign_permissions_view: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@password_expiration_check
def notification_settings_view(request):
    user = request.user
    profile = user.profile

    if request.method == "POST":
        # Classic form submission
        email_pref = request.POST.get("email_notifications") == "on"
        profile.email_notifications = email_pref
        profile.save(update_fields=["email_notifications"])
        # Optionally, create a notification for preference changes
        create_notification(
            user=user,
            title="Notification Preferences Updated",
            message="Your notification preferences have been updated.",
            notification_type="success"
        )
        messages.success(request, "Notification preferences updated.")
        return redirect('core:notification_settings')

    context = {
        "user_profile": profile,
    }
    return render(request, "core/notification_settings.html", context)

@csrf_exempt
@login_required
def update_user_preference(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=405)
    try:
        data = json.loads(request.body.decode())
        key = data.get("preference")
        value = data.get("value")
        profile = request.user.profile

        # Only allow updating certain preferences
        if key == "email_notifications":
            profile.email_notifications = bool(value) if isinstance(value, bool) else value == "true" or value is True
            profile.save(update_fields=["email_notifications"])
        else:
            return JsonResponse({"success": False, "error": "Unknown preference"}, status=400)

        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@login_required
@password_expiration_check
def privacy_settings_view(request):
    user = request.user
    profile = user.profile

    if request.method == "POST":
        # (Expand this section as you add real privacy options)
        allow_profile_discovery = request.POST.get("allow_profile_discovery") == "on"
        profile.allow_profile_discovery = allow_profile_discovery
        profile.save(update_fields=["allow_profile_discovery"])
        create_notification(
            user=user,
            title="Privacy Preferences Updated",
            message="Your privacy settings have been updated.",
            notification_type="success"
        )
        messages.success(request, "Privacy settings updated.")
        return redirect('core:privacy_settings')

    context = {
        "user_profile": profile,
    }
    return render(request, "core/privacy_settings.html", context)

@login_required
def export_data_view(request):
    """
    Exports the user's own profile and basic data as CSV.
    You can expand this to include orders, quotes, etc.
    """
    user = request.user
    profile = user.profile if hasattr(user, 'profile') else None

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{user.username}_profile.csv"'
    writer = csv.writer(response)
    
    # Write header
    writer.writerow(['Field', 'Value'])
    
    # Write user data
    writer.writerow(['Username', user.username])
    writer.writerow(['Email', user.email])
    writer.writerow(['First Name', user.first_name])
    writer.writerow(['Last Name', user.last_name])
    if profile:
        writer.writerow(['Department', profile.get_department_display()])
        writer.writerow(['User Type', profile.get_user_type_display()])
        writer.writerow(['Phone', profile.phone])
        writer.writerow(['Address', profile.address])
        writer.writerow(['Allow Profile Discovery', getattr(profile, 'allow_profile_discovery', '')])
        # Add more as needed

    return response

@login_required
def export_notifications_view(request):
    """
    Exports the current user's notifications as CSV.
    """
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{request.user.username}_notifications.csv"'
    writer = csv.writer(response)
    
    # Header
    writer.writerow(['Title', 'Message', 'Type', 'Is Read', 'Created At'])
    for notif in notifications:
        writer.writerow([
            notif.title,
            notif.message,
            notif.type,
            'Yes' if notif.is_read else 'No',
            notif.created_at.strftime('%Y-%m-%d %H:%M')
        ])
    
    return response

@login_required
def mark_all_notifications_read(request):
    """
    Marks all notifications as read for the logged-in user.
    Supports both POST (AJAX) and GET (simple link).
    """
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    # Support AJAX or plain link
    if request.is_ajax() or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    else:
        return HttpResponseRedirect(reverse('core:notifications'))

@login_required
def get_notification_details(request, notification_id):
    """
    Returns detailed info about a notification for the logged-in user (AJAX).
    """
    try:
        notif = Notification.objects.get(id=notification_id, user=request.user)
    except Notification.DoesNotExist:
        raise Http404("Notification not found")

    data = {
        'id': notif.id,
        'title': notif.title,
        'message': notif.message,
        'type': notif.type,
        'is_read': notif.is_read,
        'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M'),
        'action_url': notif.action_url,
        'action_text': notif.action_text,
    }
    return JsonResponse({'success': True, 'notification': data})

@login_required
def archive_notification(request, notification_id):
    """
    Archives a notification for the logged-in user.
    Supports both POST (AJAX) and GET (link).
    """
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.is_archived = True
    notif.save(update_fields=['is_archived'])
    if request.is_ajax() or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    else:
        return HttpResponseRedirect(reverse('core:notifications'))

@login_required
def get_notification_updates(request):
    """
    Returns unread notifications and count for the logged-in user.
    For navbar/notifications page AJAX polling.
    """
    notifications = Notification.objects.filter(
        user=request.user, is_read=False, is_archived=False
    ).order_by('-created_at')[:10]
    
    data = []
    for notif in notifications:
        data.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message[:120],
            'type': notif.type,
            'created_at': notif.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_read': notif.is_read,
            'action_url': notif.action_url,
            'action_text': notif.action_text,
        })
    return JsonResponse({
        'count': notifications.count(),
        'notifications': data
    })

@login_required
@user_passes_test(is_manager_or_admin)
def audit_log_view(request):
    logs = AuditLog.objects.select_related('user').all()

    # Filtering
    q = request.GET.get('q', '')
    action = request.GET.get('action', '')
    object_type = request.GET.get('object_type', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('from', '')
    date_to = request.GET.get('to', '')

    if q:
        logs = logs.filter(
            Q(description__icontains=q) |
            Q(user__username__icontains=q) |
            Q(object_type__icontains=q) |
            Q(object_id__icontains=q)
        )
    if action:
        logs = logs.filter(action=action)
    if object_type:
        logs = logs.filter(object_type=object_type)
    if user_id:
        logs = logs.filter(user__id=user_id)
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)

    logs = logs.order_by('-timestamp')
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        "logs": page_obj,
        "actions": AuditLog.ACTIONS,
        "object_types": AuditLog.objects.values_list('object_type', flat=True).distinct(),
        "users": AuditLog.objects.select_related('user').values('user__id', 'user__username').distinct(),
        "current_filter": {"q": q, "action": action, "object_type": object_type, "user_id": user_id, "from": date_from, "to": date_to}
    }
    
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=audit_log.csv"
        writer = csv.writer(response)
        writer.writerow(["Timestamp", "User", "Action", "Object Type", "Object ID", "Description", "IP", "User Agent"])
        for log in logs:
            writer.writerow([
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                log.user.username if log.user else "Anonymous",
                log.get_action_display(),
                log.object_type,
                log.object_id,
                log.description,
                log.ip_address,
                log.user_agent,
            ])
        return response

    return render(request, "core/audit_log.html", context)

# =====================================
# SECURITY MONITORING VIEWS
# =====================================

@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profile') and u.profile.user_type == 'it_admin'))
def security_dashboard_view(request):
    """Security monitoring dashboard"""
    from datetime import timedelta
    from django.db.models import Count
    
    # Get recent security events
    recent_events = SecurityEvent.objects.all()[:50]
    
    # Get statistics for last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    event_stats = SecurityEvent.objects.filter(
        timestamp__gte=thirty_days_ago
    ).values('event_type').annotate(count=Count('id')).order_by('-count')
    
    # Failed login attempts by IP
    failed_logins = SecurityEvent.objects.filter(
        event_type='login_failure',
        timestamp__gte=thirty_days_ago
    ).values('ip_address').annotate(count=Count('id')).order_by('-count')[:10]
    
    # Recent registrations
    recent_registrations = User.objects.filter(
        date_joined__gte=thirty_days_ago
    ).select_related('profile').order_by('-date_joined')[:20]
    
    context = {
        'recent_events': recent_events,
        'event_stats': event_stats,
        'failed_logins': failed_logins,
        'recent_registrations': recent_registrations,
    }
    
    return render(request, 'core/security_dashboard.html', context)

@require_http_methods(["GET"])
def check_email_availability(request):
    email = request.GET.get('email', '').strip()
    if not email:
        return JsonResponse({'available': False, 'message': 'Email required'})
    
    available = not User.objects.filter(email=email).exists()
    return JsonResponse({'available': available})

@login_required
@require_http_methods(["GET"])
def profile_completion_status(request):
    profile = request.user.profile
    return JsonResponse({
        'completed': profile.profile_completed,
        'completion_percentage': profile.get_completion_percentage(),
        'incomplete_fields': profile.get_incomplete_fields()
    })

@login_required
@require_http_methods(["GET"])
def user_stats_api(request):
    stats = get_user_dashboard_stats(request.user)
    return JsonResponse(stats)

