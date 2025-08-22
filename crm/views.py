import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum, Count, Avg, F, Case, When
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django.template.loader import render_to_string
from weasyprint import HTML
from io import BytesIO
import logging

from django.utils.timesince import timesince
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from core.decorators import ajax_required, password_expiration_check
from core.utils import create_notification, has_app_permission
from .models import Client, CustomerInteraction, Deal, Task
from .forms import ClientForm, CustomerInteractionForm, DealForm, TaskForm
from core.views import is_admin_user, is_manager_or_admin

logger = logging.getLogger(__name__)

# =====================================
# CRM DASHBOARD
# =====================================

@password_expiration_check
def crm_dashboard(request):
    """Main CRM dashboard with analytics and overview"""
    
    # Get basic stats
    total_clients = Client.objects.count()
    active_clients = Client.objects.filter(status__in=['prospect', 'client']).count()
    leads = Client.objects.filter(status='lead').count()
    inactive_clients = Client.objects.filter(status='inactive').count()
    
    # Get recent activity
    recent_clients = Client.objects.order_by('-created_at')[:5]
    recent_interactions = CustomerInteraction.objects.select_related('client').order_by('-created_at')[:5]
    upcoming_followups = CustomerInteraction.objects.filter(
        next_followup__isnull=False,
        next_followup__gte=timezone.now(),
        next_followup__lte=timezone.now() + timezone.timedelta(days=7)
    ).select_related('client').order_by('next_followup')[:5]
    
    # Get overdue follow-ups
    overdue_followups = CustomerInteraction.objects.filter(
        next_followup__isnull=False,
        next_followup__lt=timezone.now()
    ).select_related('client').order_by('next_followup')[:5]
    
    # Client status distribution
    status_stats = Client.objects.values('status').annotate(count=Count('id'))
    
    # Monthly client acquisition
    monthly_stats = Client.objects.extra(
        select={'month': "DATE_TRUNC('month', created_at)"}
    ).values('month').annotate(count=Count('id')).order_by('month')
    
    # Top regions
    region_stats = Client.objects.exclude(
        country__isnull=True
    ).exclude(
        country=''
    ).values('country').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    context = {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'leads': leads,
        'inactive_clients': inactive_clients,
        'recent_clients': recent_clients,
        'recent_interactions': recent_interactions,
        'upcoming_followups': upcoming_followups,
        'overdue_followups': overdue_followups,
        'status_stats': status_stats,
        'monthly_stats': monthly_stats,
        'region_stats': region_stats,
    }
    
    context.update({
    'user_task_stats': {
        'overdue_count': Task.objects.filter(
            assigned_to=request.user,
            due_date__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count(),
        'due_today': Task.objects.filter(
            assigned_to=request.user,
            due_date__date=timezone.now().date()
        ).count(),
        },
    'pipeline_stats': {
        'overdue_deals': Deal.objects.filter(
            assigned_to=request.user,
            expected_close_date__lt=timezone.now().date(),
            stage__in=['prospecting', 'qualification', 'proposal', 'negotiation']
        ).count() if not is_admin_user(request.user) else 0,
        }
    })
    
    return render(request, 'crm/dashboard.html', context)


# =====================================
# CLIENT MANAGEMENT
# =====================================

@password_expiration_check
def client_list(request):
    """Enhanced client list with filtering and search"""
    
    clients = Client.objects.all().order_by('-created_at')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        clients = clients.filter(status=status_filter)
    
    # Filter by customer type
    customer_type_filter = request.GET.get('customer_type', '')
    if customer_type_filter:
        clients = clients.filter(customer_type=customer_type_filter)
    
    # Filter by region
    region_filter = request.GET.get('region', '')
    if region_filter:
        clients = clients.filter(country=region_filter)
    
    # Sort options
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['name', '-name', 'created_at', '-created_at', 'last_contacted', '-last_contacted', 'total_value', '-total_value']:
        clients = clients.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(clients, 20)  # Show 20 clients per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options for dropdowns
    status_choices = Client.STATUS_CHOICES
    customer_type_choices = Client.CUSTOMER_TYPE_CHOICES
    regions = Client.objects.exclude(country__isnull=True).exclude(country='').values_list('country', flat=True).distinct()
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'customer_type_filter': customer_type_filter,
        'region_filter': region_filter,
        'sort_by': sort_by,
        'status_choices': status_choices,
        'customer_type_choices': customer_type_choices,
        'regions': regions,
    }
    
    return render(request, 'crm/client_list.html', context)


@password_expiration_check
def client_detail(request, client_id):
    """Detailed client view with 360° customer information"""
    
    client = get_object_or_404(Client, id=client_id)
    
    # Get all interactions for this client
    interactions = CustomerInteraction.objects.filter(
        client=client
    ).order_by('-created_at')
    
    # Get client statistics
    total_interactions = interactions.count()
    last_interaction = interactions.first()
    
    # Get upcoming and overdue follow-ups
    upcoming_followups = interactions.filter(
        next_followup__isnull=False,
        next_followup__gte=timezone.now()
    ).order_by('next_followup')
    
    overdue_followups = interactions.filter(
        next_followup__isnull=False,
        next_followup__lt=timezone.now()
    ).order_by('next_followup')
    
    # Get interaction type breakdown
    interaction_stats = interactions.values('interaction_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    context = {
        'client': client,
        'interactions': interactions[:10],  # Show last 10 interactions
        'total_interactions': total_interactions,
        'last_interaction': last_interaction,
        'upcoming_followups': upcoming_followups,
        'overdue_followups': overdue_followups,
        'interaction_stats': interaction_stats,
    }
    
    return render(request, 'crm/client_detail.html', context)


@password_expiration_check
def client_create(request):
    """Create new client with enhanced form"""
    
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                client = form.save(commit=False)
                client.created_by = request.user
                client.save()
                
                # Create initial interaction
                CustomerInteraction.objects.create(
                    client=client,
                    interaction_type='created',
                    notes=f'Client record created by {request.user.get_full_name()}',
                    created_by=request.user
                )
                
                # Create notification
                create_notification(
                    user=request.user,
                    title="New Client Added",
                    message=f"Client {client.name} has been successfully added to the system.",
                    notification_type="success"
                )
                
                logger.info(f"New client {client.name} created by {request.user.username}")
                messages.success(request, f'Client {client.name} has been added successfully.')
                
                return redirect('crm:client_detail', client_id=client.id)
    else:
        form = ClientForm()
    
    context = {'form': form}
    return render(request, 'crm/client_form.html', context)


@password_expiration_check
def client_update(request, client_id):
    """Update client information"""
    
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            with transaction.atomic():
                # Track changes
                changes = []
                for field in form.changed_data:
                    old_value = getattr(client, field)
                    new_value = form.cleaned_data[field]
                    changes.append(f"{field}: '{old_value}' → '{new_value}'")
                
                client = form.save()
                
                # Create interaction for update
                if changes:
                    CustomerInteraction.objects.create(
                        client=client,
                        interaction_type='updated',
                        notes=f'Client updated by {request.user.get_full_name()}. Changes: {", ".join(changes)}',
                        created_by=request.user
                    )
                
                logger.info(f"Client {client.name} updated by {request.user.username}")
                messages.success(request, f'Client {client.name} has been updated successfully.')
                
                return redirect('crm:client_detail', client_id=client.id)
    else:
        form = ClientForm(instance=client)
    
    context = {
        'form': form,
        'client': client,
    }
    return render(request, 'crm/client_form.html', context)


@password_expiration_check
def client_delete(request, client_id):
    """Delete client (admin only)"""
    
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        client_name = client.name
        client.delete()
        
        logger.info(f"Client {client_name} deleted by {request.user.username}")
        messages.success(request, f'Client {client_name} has been deleted.')
        
        return redirect('crm:client_list')
    
    context = {'client': client}
    return render(request, 'crm/client_confirm_delete.html', context)


# =====================================
# CUSTOMER INTERACTIONS
# =====================================

@password_expiration_check
def add_interaction(request, client_id):
    """Add new customer interaction"""
    
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = CustomerInteractionForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                interaction = form.save(commit=False)
                interaction.client = client
                interaction.created_by = request.user
                interaction.save()
                
                # Update client's last_contacted
                client.last_contacted = interaction.created_at
                if interaction.next_followup:
                    client.followup_date = interaction.next_followup
                client.save()
                
                messages.success(request, 'Interaction has been recorded successfully.')
                return redirect('crm:client_detail', client_id=client.id)
    else:
        form = CustomerInteractionForm()
    
    context = {
        'form': form,
        'client': client,
    }
    return render(request, 'crm/add_interaction.html', context)


@password_expiration_check
def interaction_list(request, client_id=None):
    """List all interactions, optionally filtered by client"""
    
    interactions = CustomerInteraction.objects.select_related('client', 'created_by').order_by('-created_at')
    
    if client_id:
        client = get_object_or_404(Client, id=client_id)
        interactions = interactions.filter(client=client)
    else:
        client = None
    
    # Filter by interaction type
    interaction_type_filter = request.GET.get('type', '')
    if interaction_type_filter:
        interactions = interactions.filter(interaction_type=interaction_type_filter)
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        interactions = interactions.filter(
            Q(notes__icontains=search_query) |
            Q(client__name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(interactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'client': client,
        'interaction_type_filter': interaction_type_filter,
        'search_query': search_query,
        'interaction_types': CustomerInteraction.INTERACTION_TYPES,
    }
    
    return render(request, 'crm/interaction_list.html', context)


# =====================================
# FOLLOW-UP MANAGEMENT
# =====================================

@password_expiration_check
def followup_list(request):
    """List all follow-ups (upcoming and overdue)"""
    
    # Get upcoming follow-ups (next 30 days)
    upcoming_followups = CustomerInteraction.objects.filter(
        next_followup__isnull=False,
        next_followup__gte=timezone.now(),
        next_followup__lte=timezone.now() + timezone.timedelta(days=30)
    ).select_related('client', 'created_by').order_by('next_followup')
    
    # Get overdue follow-ups
    overdue_followups = CustomerInteraction.objects.filter(
        next_followup__isnull=False,
        next_followup__lt=timezone.now()
    ).select_related('client', 'created_by').order_by('next_followup')
    
    context = {
        'upcoming_followups': upcoming_followups,
        'overdue_followups': overdue_followups,
    }
    
    return render(request, 'crm/followup_list.html', context)


@ajax_required
def mark_followup_complete(request, interaction_id):
    """Mark a follow-up as complete (AJAX)"""
    
    if request.method == 'POST':
        interaction = get_object_or_404(CustomerInteraction, id=interaction_id)
        
        # Clear the follow-up date
        interaction.next_followup = None
        interaction.save()
        
        # Create a new interaction record
        CustomerInteraction.objects.create(
            client=interaction.client,
            interaction_type='followup_completed',
            notes=f'Follow-up completed by {request.user.get_full_name()}',
            created_by=request.user
        )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}, status=400)


# =====================================
# ANALYTICS AND REPORTS
# =====================================

@password_expiration_check
def client_analytics(request):
    """Client analytics and reporting dashboard"""
    
    # Date range filtering
    from datetime import datetime, timedelta
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days by default
    
    date_range = request.GET.get('range', '30')
    if date_range == '7':
        start_date = end_date - timedelta(days=7)
    elif date_range == '90':
        start_date = end_date - timedelta(days=90)
    elif date_range == '365':
        start_date = end_date - timedelta(days=365)
    
    # Client acquisition over time
    acquisition_data = Client.objects.filter(
        created_at__gte=start_date
    ).extra(
        select={'date': "DATE(created_at)"}
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Status distribution
    status_distribution = Client.objects.values('status').annotate(
        count=Count('id')
    )
    
    # Customer type distribution
    type_distribution = Client.objects.values('customer_type').annotate(
        count=Count('id')
    )
    
    # Regional distribution
    regional_distribution = Client.objects.exclude(
        country__isnull=True
    ).exclude(
        country=''
    ).values('country').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Top clients by interaction count
    top_clients_by_interactions = Client.objects.annotate(
        interaction_count=Count('customerinteraction')
    ).order_by('-interaction_count')[:10]
    
    # Interaction trends
    interaction_trends = CustomerInteraction.objects.filter(
        created_at__gte=start_date
    ).extra(
        select={'date': "DATE(created_at)"}
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    context = {
        'date_range': date_range,
        'start_date': start_date,
        'end_date': end_date,
        'acquisition_data': acquisition_data,
        'status_distribution': status_distribution,
        'type_distribution': type_distribution,
        'regional_distribution': regional_distribution,
        'top_clients_by_interactions': top_clients_by_interactions,
        'interaction_trends': interaction_trends,
    }
    
    return render(request, 'crm/analytics.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff or u.profile.is_manager or u.profile.is_admin)
def performance_report(request):
    """Boardroom-scale CRM performance report with deep insights."""

    # --- Timeframes
    today = timezone.now().date()
    start_30 = today - timezone.timedelta(days=30)
    start_90 = today - timezone.timedelta(days=90)
    start_year = today.replace(month=1, day=1)

    # --- Client stats
    client_total = Client.objects.count()
    client_new_30 = Client.objects.filter(created_at__gte=start_30).count()
    client_lost_30 = Client.objects.filter(status='lost', updated_at__gte=start_30).count()
    client_by_status = Client.objects.values('status').annotate(count=Count('id'))
    top_clients = Client.objects.annotate(
        deal_value=Sum('deal__value')
    ).order_by('-deal_value')[:10]

    # --- Sales/Deals
    deal_total = Deal.objects.count()
    deals_closed_won_30 = Deal.objects.filter(stage='closed_won', actual_close_date__gte=start_30)
    deals_closed_lost_30 = Deal.objects.filter(stage='closed_lost', actual_close_date__gte=start_30)
    deals_pipeline = Deal.objects.exclude(stage__in=['closed_won', 'closed_lost'])
    pipeline_value = deals_pipeline.aggregate(total=Sum('value'))['total'] or 0
    win_rate_30 = (
        deals_closed_won_30.count() / max((deals_closed_won_30.count() + deals_closed_lost_30.count()), 1) * 100
    )
    avg_deal_size_30 = deals_closed_won_30.aggregate(avg=Avg('value'))['avg'] or 0
    sales_growth_30 = deals_closed_won_30.aggregate(total=Sum('value'))['total'] or 0

    # --- Team/Performance
    # Top performers by won deals in last 30 days
    team_performance = (
        Deal.objects.filter(stage='closed_won', actual_close_date__gte=start_30)
        .values('assigned_to__first_name', 'assigned_to__last_name')
        .annotate(won=Count('id'), value=Sum('value'))
        .order_by('-value')
    )

    # --- Tasks (Efficiency)
    overdue_tasks = Task.objects.filter(status__in=['pending', 'in_progress'], due_date__lt=timezone.now()).count()
    completed_tasks_30 = Task.objects.filter(status='completed', completed_at__gte=start_30).count()
    avg_task_completion_time = (
        Task.objects.filter(status='completed', completed_at__gte=start_30)
        .annotate(duration=F('completed_at') - F('created_at'))
        .aggregate(avg=Avg('duration'))
    )['avg']

    # --- Activity/Engagement
    interactions_30 = CustomerInteraction.objects.filter(created_at__gte=start_30).count()
    avg_interaction_per_client = (
        CustomerInteraction.objects.filter(created_at__gte=start_30)
        .values('client').annotate(count=Count('id')).aggregate(avg=Avg('count'))['avg']
    )

    if avg_task_completion_time:
        avg_task_completion_time_str = timesince(timezone.now() - avg_task_completion_time)
    else:
        avg_task_completion_time_str = None

    # --- Trends over time for plotting (for future: plot with JS)
    deals_trend_30 = (
        Deal.objects.filter(created_at__gte=start_30)
        .extra({'date': "date(created_at)"})
        .values('date').annotate(count=Count('id')).order_by('date')
    )

    # --- Risk flags
    stagnant_clients = Client.objects.filter(
        last_contacted__lt=timezone.now() - timezone.timedelta(days=60),
        status__in=['prospect', 'client']
    )[:10]

    # --- Context for template
    context = {
        'client_total': client_total,
        'client_new_30': client_new_30,
        'client_lost_30': client_lost_30,
        'client_by_status': list(client_by_status),
        'top_clients': top_clients,
        'deal_total': deal_total,
        'deals_closed_won_30': deals_closed_won_30.count(),
        'deals_closed_lost_30': deals_closed_lost_30.count(),
        'pipeline_value': pipeline_value,
        'win_rate_30': round(win_rate_30, 1),
        'avg_deal_size_30': avg_deal_size_30,
        'sales_growth_30': sales_growth_30,
        'team_performance': team_performance,
        'overdue_tasks': overdue_tasks,
        'completed_tasks_30': completed_tasks_30,
        'avg_task_completion_time': avg_task_completion_time,
        'interactions_30': interactions_30,
        'avg_interaction_per_client': avg_interaction_per_client,
        'deals_trend_30': list(deals_trend_30),
        'stagnant_clients': stagnant_clients,
        'start_30': start_30,
        'today': today,
    }
    return render(request, "crm/performance_report.html", context)


@login_required
def export_performance_pdf(request):
    response = performance_report(request)
    html = render_to_string("crm/performance_report.html", response.context_data)

    pdf_file = HTML(string=html, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="performance_report.pdf"'
    return response

@login_required
def export_performance_excel(request):
    report = performance_report(request)
    context = report.context_data

    # Flatten context data to a dict of single-row stats
    data = {
        "Total Clients": context['client_total'],
        "New Clients (30d)": context['client_new_30'],
        "Lost Clients (30d)": context['client_lost_30'],
        "Deals Closed (Won 30d)": context['deals_closed_won_30'],
        "Deals Closed (Lost 30d)": context['deals_closed_lost_30'],
        "Win Rate (%)": context['win_rate_30'],
        "Pipeline Value": context['pipeline_value'],
        "Avg Deal Size (30d)": context['avg_deal_size_30'],
        "Sales Growth (30d)": context['sales_growth_30'],
        "Tasks Completed (30d)": context['completed_tasks_30'],
        "Overdue Tasks": context['overdue_tasks'],
        "Avg Task Completion": context['avg_task_completion_time'],
        "Interactions (30d)": context['interactions_30'],
        "Avg Interactions per Client": context['avg_interaction_per_client'],
    }

    df = pd.DataFrame([data])
    buffer = BytesIO()
    df.to_excel(buffer, index=False)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="performance_report.xlsx"'
    return response


# =====================================
# AJAX UTILITIES
# =====================================

@ajax_required
def search_clients(request):
    """AJAX client search for typeahead functionality"""
    
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'clients': []})
    
    clients = Client.objects.filter(
        Q(name__icontains=query) |
        Q(email__icontains=query) |
        Q(company__icontains=query)
    )[:10]
    
    client_data = [{
        'id': client.id,
        'name': client.name,
        'email': client.email,
        'company': client.company,
        'status': client.get_status_display()
    } for client in clients]
    
    return JsonResponse({'clients': client_data})


@ajax_required
def client_quick_stats(request, client_id):
    """Get quick stats for a client (AJAX)"""
    
    client = get_object_or_404(Client, id=client_id)
    
    interactions_count = CustomerInteraction.objects.filter(client=client).count()
    last_interaction = CustomerInteraction.objects.filter(client=client).order_by('-created_at').first()
    
    stats = {
        'total_interactions': interactions_count,
        'last_interaction_date': last_interaction.created_at.strftime('%Y-%m-%d') if last_interaction else None,
        'last_interaction_type': last_interaction.get_interaction_type_display() if last_interaction else None,
        'status': client.get_status_display(),
        'customer_type': client.get_customer_type_display(),
    }
    
    return JsonResponse(stats)

# =====================================
# DEAL MANAGEMENT VIEWS
# =====================================

@password_expiration_check
def deal_list(request):
    """
    Comprehensive deal list with advanced filtering and pipeline visualization.
    
    This view provides sales team members with a complete overview of their
    sales pipeline, allowing them to track opportunities from prospecting
    through closing.
    """
    
    # Start with base queryset, optimizing for performance
    deals = Deal.objects.select_related('client', 'assigned_to').order_by('-created_at')
    
    # Apply user-based filtering (non-admins see only their deals)
    if not is_admin_user(request.user):
        deals = deals.filter(
            Q(assigned_to=request.user) | Q(created_by=request.user)
        )
    
    # Search functionality across multiple fields
    search_query = request.GET.get('search', '')
    if search_query:
        deals = deals.filter(
            Q(title__icontains=search_query) |
            Q(client__name__icontains=search_query) |
            Q(client__company__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Stage filtering for pipeline management
    stage_filter = request.GET.get('stage', '')
    if stage_filter:
        deals = deals.filter(stage=stage_filter)
    
    # Priority filtering for focus management
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        deals = deals.filter(priority=priority_filter)
    
    # Assigned user filtering (for managers)
    assigned_filter = request.GET.get('assigned', '')
    if assigned_filter:
        deals = deals.filter(assigned_to_id=assigned_filter)
    
    # Value range filtering
    min_value = request.GET.get('min_value', '')
    max_value = request.GET.get('max_value', '')
    if min_value:
        try:
            deals = deals.filter(value__gte=float(min_value))
        except ValueError:
            pass
    if max_value:
        try:
            deals = deals.filter(value__lte=float(max_value))
        except ValueError:
            pass
    
    # Close date filtering
    close_date_filter = request.GET.get('close_date', '')
    if close_date_filter == 'overdue':
        deals = deals.filter(
            expected_close_date__lt=timezone.now().date(),
            stage__in=['prospecting', 'qualification', 'proposal', 'negotiation']
        )
    elif close_date_filter == 'this_month':
        current_month = timezone.now().replace(day=1)
        deals = deals.filter(expected_close_date__gte=current_month)
    elif close_date_filter == 'this_quarter':
        # Calculate current quarter start
        current_month = timezone.now().month
        quarter_start_month = ((current_month - 1) // 3) * 3 + 1
        quarter_start = timezone.now().replace(month=quarter_start_month, day=1)
        deals = deals.filter(expected_close_date__gte=quarter_start)
    
    # Sorting options
    sort_by = request.GET.get('sort', '-created_at')
    valid_sorts = ['title', '-title', 'value', '-value', 'expected_close_date', 
                   '-expected_close_date', 'created_at', '-created_at', 'stage', '-stage']
    if sort_by in valid_sorts:
        deals = deals.order_by(sort_by)
    
    # Calculate pipeline statistics
    pipeline_stats = {
        'total_deals': deals.count(),
        'total_value': deals.aggregate(Sum('value'))['value__sum'] or 0,
        'weighted_value': deals.aggregate(
            weighted=Sum(F('value') * F('probability') / 100)
        )['weighted'] or 0,
        'avg_deal_size': deals.aggregate(Avg('value'))['value__avg'] or 0,
    }
    
    # Stage breakdown for pipeline visualization
    stage_breakdown = deals.values('stage').annotate(
        count=Count('id'),
        total_value=Sum('value'),
        weighted_value=Sum(F('value') * F('probability') / 100)
    ).order_by('stage')
    
    # Pagination
    paginator = Paginator(deals, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options for dropdowns
    available_stages = Deal.STAGE_CHOICES
    available_priorities = Deal.PRIORITY_CHOICES
    
    # Get team members for assignment filter (if user has permission)
    team_members = []
    if is_manager_or_admin(request.user):
        team_members = User.objects.filter(
            profile__user_type__in=['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin']
        ).order_by('first_name', 'last_name')
    
    context = {
        'page_obj': page_obj,
        'pipeline_stats': pipeline_stats,
        'stage_breakdown': stage_breakdown,
        
        # Filter values for form persistence
        'search_query': search_query,
        'stage_filter': stage_filter,
        'priority_filter': priority_filter,
        'assigned_filter': assigned_filter,
        'min_value': min_value,
        'max_value': max_value,
        'close_date_filter': close_date_filter,
        'sort_by': sort_by,
        
        # Filter options
        'available_stages': available_stages,
        'available_priorities': available_priorities,
        'team_members': team_members,
    }
    
    return render(request, 'crm/deal_list.html', context)


@password_expiration_check
def deal_detail(request, deal_id):
    """
    Detailed deal view with complete opportunity information and related activities.
    
    This view provides a 360-degree view of a sales opportunity, including
    timeline, tasks, interactions, and probability analysis.
    """
    
    deal = get_object_or_404(Deal, id=deal_id)
    
    # Permission check: users can only view deals they're involved with
    if not is_admin_user(request.user):
        if deal.assigned_to != request.user and deal.created_by != request.user:
            messages.error(request, 'You do not have permission to view this deal.')
            return redirect('crm:deal_list')
    
    # Get related tasks
    deal_tasks = Task.objects.filter(deal=deal).order_by('-created_at')
    
    # Get client interactions related to this deal
    # (interactions that happened during the deal lifecycle)
    client_interactions = CustomerInteraction.objects.filter(
        client=deal.client,
        created_at__gte=deal.created_at
    ).order_by('-created_at')[:10]
    
    # Calculate deal metrics
    days_to_close = deal.days_until_close
    deal_age = (timezone.now().date() - deal.created_at.date()).days
    
    # Deal stage progression (simplified timeline)
    stage_progression = [
        {'stage': 'prospecting', 'label': 'Prospecting', 'completed': True},
        {'stage': 'qualification', 'label': 'Qualification', 'completed': deal.stage in ['qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost']},
        {'stage': 'proposal', 'label': 'Proposal', 'completed': deal.stage in ['proposal', 'negotiation', 'closed_won', 'closed_lost']},
        {'stage': 'negotiation', 'label': 'Negotiation', 'completed': deal.stage in ['negotiation', 'closed_won', 'closed_lost']},
        {'stage': 'closed_won', 'label': 'Closed', 'completed': deal.stage in ['closed_won', 'closed_lost']},
    ]
    
    # Mark current stage
    for stage in stage_progression:
        stage['current'] = stage['stage'] == deal.stage
    
    context = {
        'deal': deal,
        'deal_tasks': deal_tasks,
        'client_interactions': client_interactions,
        'days_to_close': days_to_close,
        'deal_age': deal_age,
        'stage_progression': stage_progression,
    }
    
    return render(request, 'crm/deal_detail.html', context)


@password_expiration_check
def deal_create(request):
    """
    Create new sales deal with intelligent defaults and client context.
    
    This view handles deal creation with smart defaults based on client
    information and user preferences.
    """
    
    # Get client if specified in URL parameters
    client_id = request.GET.get('client_id')
    client = None
    if client_id:
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            messages.warning(request, 'Specified client not found.')
    
    if request.method == 'POST':
        form = DealForm(request.POST, client=client)
        if form.is_valid():
            with transaction.atomic():
                deal = form.save(commit=False)
                deal.created_by = request.user
                
                # Set intelligent defaults
                if not deal.assigned_to:
                    deal.assigned_to = request.user
                
                deal.save()
                
                # Create initial task for deal follow-up
                Task.objects.create(
                    title=f"Follow up on {deal.title}",
                    description=f"Initial follow-up task for deal: {deal.title}",
                    deal=deal,
                    client=deal.client,
                    priority='medium',
                    assigned_to=deal.assigned_to,
                    due_date=timezone.now() + timezone.timedelta(days=3),
                    created_by=request.user
                )
                
                # Create interaction record
                CustomerInteraction.objects.create(
                    client=deal.client,
                    interaction_type='proposal',
                    notes=f'New deal created: {deal.title} (${deal.value:,.2f})',
                    created_by=request.user
                )
                
                # Send notification to assigned user (if different from creator)
                if deal.assigned_to != request.user:
                    create_notification(
                        user=deal.assigned_to,
                        title="New Deal Assigned",
                        message=f"You have been assigned a new deal: {deal.title} (${deal.value:,.2f})",
                        notification_type="info"
                    )
                
                logger.info(f"New deal '{deal.title}' created by {request.user.username}")
                messages.success(request, f'Deal "{deal.title}" has been created successfully.')
                
                return redirect('crm:deal_detail', deal_id=deal.id)
    else:
        form = DealForm(client=client)
        
        # Set initial values if client is specified
        if client:
            form.fields['value'].initial = 5000  # Default deal size
            form.fields['currency'].initial = client.currency_preference
    
    context = {
        'form': form,
        'client': client,
    }
    return render(request, 'crm/deal_form.html', context)


@password_expiration_check
def deal_update(request, deal_id):
    """
    Update deal information with change tracking and stage progression logic.
    
    This view handles deal updates while maintaining an audit trail and
    automatically triggering appropriate business logic for stage changes.
    """
    
    deal = get_object_or_404(Deal, id=deal_id)
    
    # Permission check
    if not is_admin_user(request.user):
        if deal.assigned_to != request.user and deal.created_by != request.user:
            messages.error(request, 'You do not have permission to edit this deal.')
            return redirect('crm:deal_detail', deal_id=deal.id)
    
    if request.method == 'POST':
        form = DealForm(request.POST, instance=deal)
        if form.is_valid():
            with transaction.atomic():
                # Track important changes
                old_stage = deal.stage
                old_probability = deal.probability
                old_value = deal.value
                old_assigned = deal.assigned_to
                
                deal = form.save()
                
                # Handle stage changes
                if old_stage != deal.stage:
                    # Create interaction for stage change
                    CustomerInteraction.objects.create(
                        client=deal.client,
                        interaction_type='proposal',
                        notes=f'Deal stage updated: {old_stage} → {deal.stage}',
                        created_by=request.user
                    )
                    
                    # Handle closed deals
                    if deal.stage == 'closed_won':
                        deal.actual_close_date = timezone.now().date()
                        
                        # Update client status if they become a customer
                        if deal.client.status in ['lead', 'prospect']:
                            deal.client.status = 'client'
                            deal.client.save()
                        
                        # Create celebration notification
                        create_notification(
                            user=deal.assigned_to,
                            title="Deal Won! 🎉",
                            message=f"Congratulations! Deal '{deal.title}' has been closed successfully for ${deal.value:,.2f}",
                            notification_type="success"
                        )
                        
                    elif deal.stage == 'closed_lost':
                        deal.actual_close_date = timezone.now().date()
                        
                        # Create follow-up task for lost deal analysis
                        Task.objects.create(
                            title=f"Analyze lost deal: {deal.title}",
                            description="Review why this deal was lost and document lessons learned",
                            deal=deal,
                            client=deal.client,
                            priority='low',
                            assigned_to=deal.assigned_to,
                            due_date=timezone.now() + timezone.timedelta(days=7),
                            created_by=request.user
                        )
                
                # Handle assignment changes
                if old_assigned != deal.assigned_to and deal.assigned_to:
                    create_notification(
                        user=deal.assigned_to,
                        title="Deal Reassigned to You",
                        message=f"Deal '{deal.title}' has been assigned to you",
                        notification_type="info"
                    )
                
                # Handle significant value changes (>20%)
                if old_value and abs(deal.value - old_value) / old_value > 0.2:
                    CustomerInteraction.objects.create(
                        client=deal.client,
                        interaction_type='proposal',
                        notes=f'Deal value updated: ${old_value:,.2f} → ${deal.value:,.2f}',
                        created_by=request.user
                    )
                
                deal.save()  # Save again to capture any automatic updates
                
                logger.info(f"Deal '{deal.title}' updated by {request.user.username}")
                messages.success(request, f'Deal "{deal.title}" has been updated successfully.')
                
                return redirect('crm:deal_detail', deal_id=deal.id)
    else:
        form = DealForm(instance=deal)
    
    context = {
        'form': form,
        'deal': deal,
    }
    return render(request, 'crm/deal_form.html', context)


@password_expiration_check
def deal_delete(request, deal_id):
    """
    Delete deal with proper cleanup and audit trail.
    
    Only administrators can delete deals to maintain data integrity
    and audit trail requirements.
    """
    
    deal = get_object_or_404(Deal, id=deal_id)
    
    if request.method == 'POST':
        with transaction.atomic():
            deal_title = deal.title
            client_name = deal.client.name
            
            # Create interaction record before deletion
            CustomerInteraction.objects.create(
                client=deal.client,
                interaction_type='proposal',
                notes=f'Deal "{deal_title}" deleted by administrator {request.user.get_full_name()}',
                created_by=request.user
            )
            
            # Update related tasks to remove deal reference
            Task.objects.filter(deal=deal).update(deal=None)
            
            deal.delete()
            
            logger.warning(f"Deal '{deal_title}' deleted by {request.user.username}")
            messages.success(request, f'Deal "{deal_title}" has been deleted.')
        
        return redirect('crm:deal_list')
    
    context = {'deal': deal}
    return render(request, 'crm/deal_confirm_delete.html', context)

# =====================================
# TASK MANAGEMENT VIEWS
# =====================================

@password_expiration_check
def task_list(request):
    """
    Comprehensive task management with intelligent prioritization and filtering.
    
    This view serves as a productivity dashboard where team members can see
    all their tasks organized by priority, due date, and relationship to
    clients and deals.
    """
    
    # Start with base queryset optimized for performance
    tasks = Task.objects.select_related('client', 'deal', 'assigned_to').order_by('due_date', '-priority')
    
    # Apply user-based filtering (users see tasks assigned to them or created by them)
    if not is_admin_user(request.user):
        tasks = tasks.filter(
            Q(assigned_to=request.user) | Q(created_by=request.user)
        )
    
    # Search functionality across multiple fields
    search_query = request.GET.get('search', '')
    if search_query:
        tasks = tasks.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(client__name__icontains=search_query) |
            Q(deal__title__icontains=search_query)
        )
    
    # Status filtering for workflow management
    status_filter = request.GET.get('status', '')
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    elif status_filter != 'all':
        # Default to showing only active tasks
        tasks = tasks.exclude(status__in=['completed', 'cancelled'])
    
    # Priority filtering for focus management
    priority_filter = request.GET.get('priority', '')
    if priority_filter:
        tasks = tasks.filter(priority=priority_filter)
    
    # Due date filtering for time management
    due_filter = request.GET.get('due', '')
    today = timezone.now().date()
    if due_filter == 'overdue':
        tasks = tasks.filter(
            due_date__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        )
    elif due_filter == 'today':
        tasks = tasks.filter(due_date__date=today)
    elif due_filter == 'tomorrow':
        tasks = tasks.filter(due_date__date=today + timezone.timedelta(days=1))
    elif due_filter == 'this_week':
        week_end = today + timezone.timedelta(days=7)
        tasks = tasks.filter(due_date__date__lte=week_end)
    elif due_filter == 'next_week':
        week_start = today + timezone.timedelta(days=7)
        week_end = week_start + timezone.timedelta(days=7)
        tasks = tasks.filter(due_date__date__range=[week_start, week_end])
    
    # Client filtering for relationship management
    client_filter = request.GET.get('client', '')
    if client_filter:
        try:
            client_id = int(client_filter)
            tasks = tasks.filter(client_id=client_id)
        except (ValueError, TypeError):
            pass
    
    # Deal filtering for opportunity management
    deal_filter = request.GET.get('deal', '')
    if deal_filter:
        try:
            deal_id = int(deal_filter)
            tasks = tasks.filter(deal_id=deal_id)
        except (ValueError, TypeError):
            pass
    
    # Assigned user filtering (for managers)
    assigned_filter = request.GET.get('assigned', '')
    if assigned_filter:
        tasks = tasks.filter(assigned_to_id=assigned_filter)
    
    # Sorting options
    sort_by = request.GET.get('sort', 'due_date')
    valid_sorts = ['title', '-title', 'due_date', '-due_date', 'priority', '-priority', 
                   'created_at', '-created_at', 'status', '-status']
    if sort_by in valid_sorts:
        # Special handling for priority sorting (urgent > high > medium > low)
        if sort_by == 'priority':
            tasks = tasks.extra(
                select={'priority_order': "CASE WHEN priority='urgent' THEN 1 WHEN priority='high' THEN 2 WHEN priority='medium' THEN 3 ELSE 4 END"}
            ).order_by('priority_order', 'due_date')
        elif sort_by == '-priority':
            tasks = tasks.extra(
                select={'priority_order': "CASE WHEN priority='urgent' THEN 1 WHEN priority='high' THEN 2 WHEN priority='medium' THEN 3 ELSE 4 END"}
            ).order_by('-priority_order', 'due_date')
        else:
            tasks = tasks.order_by(sort_by)
    
    # Calculate productivity statistics
    task_stats = {
        'total_tasks': tasks.count(),
        'overdue_tasks': tasks.filter(
            due_date__lt=timezone.now(),
            status__in=['pending', 'in_progress']
        ).count(),
        'due_today': tasks.filter(due_date__date=today).count(),
        'completed_this_week': Task.objects.filter(
            assigned_to=request.user,
            status='completed',
            completed_at__gte=today - timezone.timedelta(days=7)
        ).count() if not request.user.profile.is_admin else 0,
    }
    
    # Priority breakdown for visual indicators
    priority_breakdown = tasks.values('priority').annotate(
        count=Count('id')
    ).order_by('priority')
    
    # Status breakdown for workflow analysis
    status_breakdown = tasks.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Pagination
    paginator = Paginator(tasks, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options for dropdowns
    available_statuses = Task.STATUS_CHOICES
    available_priorities = Task.PRIORITY_CHOICES
    
    # Get clients and deals for filtering
    user_clients = Client.objects.all() if is_admin_user(request.user) else Client.objects.filter(
        Q(assigned_to=request.user) | Q(customerinteraction__created_by=request.user)
    ).distinct()

    user_deals = Deal.objects.all() if is_admin_user(request.user) else Deal.objects.filter(
        Q(assigned_to=request.user) | Q(created_by=request.user)
    )
    
    # Get team members for assignment filter (if user has permission)
    team_members = []
    if is_manager_or_admin(request.user):
        team_members = User.objects.filter(
            profile__user_type__in=['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin']
        ).order_by('first_name', 'last_name')
    
    context = {
        'page_obj': page_obj,
        'task_stats': task_stats,
        'priority_breakdown': priority_breakdown,
        'status_breakdown': status_breakdown,
        
        # Filter values for form persistence
        'search_query': search_query,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'due_filter': due_filter,
        'client_filter': client_filter,
        'deal_filter': deal_filter,
        'assigned_filter': assigned_filter,
        'sort_by': sort_by,
        
        # Filter options
        'available_statuses': available_statuses,
        'available_priorities': available_priorities,
        'user_clients': user_clients,
        'user_deals': user_deals,
        'team_members': team_members,
    }
    
    return render(request, 'crm/task_list.html', context)


@password_expiration_check
def task_detail(request, task_id):
    """
    Detailed task view with context and relationship information.
    
    This view provides complete context around a task, including its
    relationship to clients and deals, and allows for quick status updates.
    """
    
    task = get_object_or_404(Task, id=task_id)
    
    # Permission check: users can only view tasks they're involved with
    if not is_admin_user(request.user):
        if task.assigned_to != request.user and task.created_by != request.user:
            messages.error(request, 'You do not have permission to view this task.')
            return redirect('crm:task_list')
    
    # Get related information for context
    related_tasks = []
    if task.client:
        related_tasks = Task.objects.filter(
            client=task.client
        ).exclude(id=task.id).order_by('-created_at')[:5]
    
    # Get recent client interactions for context
    client_interactions = []
    if task.client:
        client_interactions = CustomerInteraction.objects.filter(
            client=task.client
        ).order_by('-created_at')[:5]
    
    # Calculate task metrics
    task_age = (timezone.now() - task.created_at).days
    time_until_due = None
    if task.due_date:
        time_until_due = (task.due_date - timezone.now()).days
    
    context = {
        'task': task,
        'related_tasks': related_tasks,
        'client_interactions': client_interactions,
        'task_age': task_age,
        'time_until_due': time_until_due,
    }
    
    return render(request, 'crm/task_detail.html', context)


@password_expiration_check
def task_create(request):
    """
    Create new task with intelligent context and assignment.
    
    This view handles task creation with smart defaults based on the
    context (client, deal) and user preferences.
    """
    
    # Get context from URL parameters
    client_id = request.GET.get('client_id')
    deal_id = request.GET.get('deal_id')
    
    client = None
    deal = None
    
    if client_id:
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            messages.warning(request, 'Specified client not found.')
    
    if deal_id:
        try:
            deal = Deal.objects.get(id=deal_id)
            # If deal is specified, automatically set the client
            if not client:
                client = deal.client
        except Deal.DoesNotExist:
            messages.warning(request, 'Specified deal not found.')
    
    if request.method == 'POST':
        form = TaskForm(request.POST, client=client, deal=deal, current_user=request.user)
        if form.is_valid():
            with transaction.atomic():
                task = form.save(commit=False)
                task.created_by = request.user
                
                # Set intelligent defaults
                if not task.assigned_to:
                    task.assigned_to = request.user
                
                # Set default due date if not specified
                if not task.due_date:
                    # Default to 3 days for high priority, 7 days for others
                    days_ahead = 3 if task.priority in ['high', 'urgent'] else 7
                    task.due_date = timezone.now() + timezone.timedelta(days=days_ahead)
                
                task.save()
                
                # Create interaction record if related to client
                if task.client:
                    CustomerInteraction.objects.create(
                        client=task.client,
                        interaction_type='task',
                        notes=f'Task created: {task.title}',
                        created_by=request.user
                    )
                
                # Send notification to assigned user (if different from creator)
                if task.assigned_to != request.user:
                    create_notification(
                        user=task.assigned_to,
                        title="New Task Assigned",
                        message=f"You have been assigned a new task: {task.title}",
                        notification_type="info"
                    )
                
                logger.info(f"New task '{task.title}' created by {request.user.username}")
                messages.success(request, f'Task "{task.title}" has been created successfully.')
                
                return redirect('crm:task_detail', task_id=task.id)
    else:
        form = TaskForm(client=client, deal=deal, current_user=request.user)
        
        # Set context-based defaults
        if deal:
            form.fields['title'].initial = f"Follow up on {deal.title}"
            form.fields['description'].initial = f"Follow-up task for deal: {deal.title}"
        elif client:
            form.fields['title'].initial = f"Contact {client.name}"
            form.fields['description'].initial = f"Reach out to {client.name}"
    
    context = {
        'form': form,
        'client': client,
        'deal': deal,
    }
    return render(request, 'crm/task_form.html', context)


@password_expiration_check
def task_update(request, task_id):
    """
    Update task with status change handling and productivity tracking.
    
    This view handles task updates while maintaining audit trails and
    automatically triggering appropriate business logic for status changes.
    """
    
    task = get_object_or_404(Task, id=task_id)
    
    # Permission check
    if not is_admin_user(request.user):
        if task.assigned_to != request.user and task.created_by != request.user:
            messages.error(request, 'You do not have permission to edit this task.')
            return redirect('crm:task_detail', task_id=task.id)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, current_user=request.user)
        if form.is_valid():
            with transaction.atomic():
                # Track important changes
                old_status = task.status
                old_priority = task.priority
                old_assigned = task.assigned_to
                old_due_date = task.due_date
                
                task = form.save()
                
                # Handle status changes
                if old_status != task.status:
                    if task.status == 'completed':
                        task.completed_at = timezone.now()
                        
                        # Create celebration notification for task completion
                        create_notification(
                            user=task.assigned_to,
                            title="Task Completed! ✅",
                            message=f"Task '{task.title}' has been marked as completed.",
                            notification_type="success"
                        )
                        
                        # Create interaction record if related to client
                        if task.client:
                            CustomerInteraction.objects.create(
                                client=task.client,
                                interaction_type='task',
                                notes=f'Task completed: {task.title}',
                                created_by=request.user
                            )
                    
                    elif task.status == 'cancelled':
                        # Create interaction record for cancelled task
                        if task.client:
                            CustomerInteraction.objects.create(
                                client=task.client,
                                interaction_type='task',
                                notes=f'Task cancelled: {task.title}',
                                created_by=request.user
                            )
                
                # Handle assignment changes
                if old_assigned != task.assigned_to and task.assigned_to:
                    create_notification(
                        user=task.assigned_to,
                        title="Task Reassigned to You",
                        message=f"Task '{task.title}' has been assigned to you",
                        notification_type="info"
                    )
                
                # Handle priority escalation
                if old_priority != task.priority and task.priority == 'urgent':
                    create_notification(
                        user=task.assigned_to,
                        title="Urgent Task Priority! 🚨",
                        message=f"Task '{task.title}' has been escalated to urgent priority",
                        notification_type="warning"
                    )
                
                # Handle due date changes
                if old_due_date != task.due_date and task.due_date:
                    if task.due_date < timezone.now() + timezone.timedelta(hours=24):
                        create_notification(
                            user=task.assigned_to,
                            title="Task Due Soon",
                            message=f"Task '{task.title}' is due within 24 hours",
                            notification_type="warning"
                        )
                
                task.save()  # Save again to capture any automatic updates
                
                logger.info(f"Task '{task.title}' updated by {request.user.username}")
                messages.success(request, f'Task "{task.title}" has been updated successfully.')
                
                return redirect('crm:task_detail', task_id=task.id)
    else:
        form = TaskForm(instance=task, current_user=request.user)
    
    context = {
        'form': form,
        'task': task,
    }
    return render(request, 'crm/task_form.html', context)


@ajax_required
def task_complete(request, task_id):
    """
    Quick task completion endpoint for AJAX requests.
    
    This provides a streamlined way to mark tasks as complete from
    list views and dashboard widgets without full page reloads.
    """
    
    if request.method == 'POST':
        task = get_object_or_404(Task, id=task_id)
        
        # Permission check
        if not is_admin_user(request.user):
            if task.assigned_to != request.user and task.created_by != request.user:
                return JsonResponse({'success': False, 'error': 'Permission denied'})
        
        with transaction.atomic():
            # Mark task as completed
            task.mark_completed()
            
            # Create interaction record if related to client
            if task.client:
                CustomerInteraction.objects.create(
                    client=task.client,
                    interaction_type='task',
                    notes=f'Task completed: {task.title}',
                    created_by=request.user
                )
            
            # Send completion notification
            create_notification(
                user=task.assigned_to,
                title="Task Completed! ✅",
                message=f"Task '{task.title}' has been marked as completed.",
                notification_type="success"
            )
        
        return JsonResponse({
            'success': True,
            'message': f'Task "{task.title}" marked as completed.',
            'completed_at': task.completed_at.strftime('%Y-%m-%d %H:%M') if task.completed_at else None
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@password_expiration_check
def task_delete(request, task_id):
    """
    Delete task with proper cleanup and audit trail.
    
    Only administrators can delete tasks to maintain productivity
    tracking and audit trail requirements.
    """
    
    task = get_object_or_404(Task, id=task_id)
    
    if request.method == 'POST':
        with transaction.atomic():
            task_title = task.title
            client_name = task.client.name if task.client else 'No client'
            
            # Create interaction record before deletion (if related to client)
            if task.client:
                CustomerInteraction.objects.create(
                    client=task.client,
                    interaction_type='task',
                    notes=f'Task "{task_title}" deleted by administrator {request.user.get_full_name()}',
                    created_by=request.user
                )
            
            task.delete()
            
            logger.warning(f"Task '{task_title}' deleted by {request.user.username}")
            messages.success(request, f'Task "{task_title}" has been deleted.')
        
        return redirect('crm:task_list')
    
    context = {'task': task}
    return render(request, 'crm/task_confirm_delete.html', context)


# =====================================
# ADDITIONAL UTILITY VIEWS FOR TASKS AND DEALS
# =====================================

@ajax_required
def deal_quick_stats(request, deal_id):
    """Get quick statistics for a deal (AJAX endpoint)"""
    
    deal = get_object_or_404(Deal, id=deal_id)
    
    # Permission check
    if not is_admin_user(request.user):
        if deal.assigned_to != request.user and deal.created_by != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    # Get related task count
    task_count = Task.objects.filter(deal=deal).count()
    completed_tasks = Task.objects.filter(deal=deal, status='completed').count()
    
    stats = {
        'value': f"${deal.value:,.2f}",
        'weighted_value': f"${deal.weighted_value:,.2f}",
        'stage': deal.get_stage_display(),
        'probability': f"{deal.probability}%",
        'days_until_close': deal.days_until_close,
        'is_overdue': deal.is_overdue,
        'task_count': task_count,
        'completed_tasks': completed_tasks,
        'task_completion_rate': f"{(completed_tasks/task_count*100):.0f}%" if task_count > 0 else "0%"
    }
    
    return JsonResponse({'success': True, 'stats': stats})


@ajax_required
def task_quick_stats(request, task_id):
    """Get quick statistics for a task (AJAX endpoint)"""
    
    task = get_object_or_404(Task, id=task_id)
    
    # Permission check
    if not is_admin_user(request.user):
        if task.assigned_to != request.user and task.created_by != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    stats = {
        'status': task.get_status_display(),
        'priority': task.get_priority_display(),
        'days_until_due': task.days_until_due,
        'is_overdue': task.is_overdue,
        'client': task.client.name if task.client else None,
        'deal': task.deal.title if task.deal else None,
        'assigned_to': task.assigned_to.get_full_name() if task.assigned_to else None,
    }
    
    return JsonResponse({'success': True, 'stats': stats})
