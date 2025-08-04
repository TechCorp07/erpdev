from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Sum
from django.contrib.admin import SimpleListFilter
from .models import (
    Client, CustomerInteraction, Deal, Task, ClientNote, CRMSettings
)

class LastContactedFilter(SimpleListFilter):
    """Filter clients by last contacted date"""
    title = 'Last Contacted'
    parameter_name = 'last_contacted'

    def lookups(self, request, model_admin):
        return (
            ('never', 'Never contacted'),
            ('week', 'Within last week'),
            ('month', 'Within last month'),
            ('quarter', 'Within last quarter'),
            ('overdue', 'Overdue follow-up'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'never':
            return queryset.filter(last_contacted__isnull=True)
        elif self.value() == 'week':
            return queryset.filter(last_contacted__gte=now - timezone.timedelta(days=7))
        elif self.value() == 'month':
            return queryset.filter(last_contacted__gte=now - timezone.timedelta(days=30))
        elif self.value() == 'quarter':
            return queryset.filter(last_contacted__gte=now - timezone.timedelta(days=90))
        elif self.value() == 'overdue':
            return queryset.filter(followup_date__lt=now, followup_date__isnull=False)


class LeadScoreFilter(SimpleListFilter):
    """Filter clients by lead score"""
    title = 'Lead Score'
    parameter_name = 'lead_score'

    def lookups(self, request, model_admin):
        return (
            ('high', 'High (80-100)'),
            ('medium', 'Medium (50-79)'),
            ('low', 'Low (0-49)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'high':
            return queryset.filter(lead_score__gte=80)
        elif self.value() == 'medium':
            return queryset.filter(lead_score__gte=50, lead_score__lt=80)
        elif self.value() == 'low':
            return queryset.filter(lead_score__lt=50)


class InteractionInline(admin.TabularInline):
    """Inline display of customer interactions"""
    model = CustomerInteraction
    fields = ('interaction_type', 'notes', 'outcome', 'next_followup', 'created_at')
    readonly_fields = ('created_at',)
    extra = 0
    max_num = 5  # Show only last 5 interactions
    ordering = ('-created_at',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('created_by')


class TaskInline(admin.TabularInline):
    """Inline display of tasks"""
    model = Task
    fields = ('title', 'priority', 'status', 'due_date', 'assigned_to')
    extra = 0
    max_num = 3


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'company', 'email', 'phone', 'status_badge', 'customer_type_badge', 
        'priority_badge', 'lead_score_badge', 'last_contacted_display', 
        'total_interactions', 'total_value_display', 'created_at'
    )
    
    list_filter = (
        'status', 'customer_type', 'priority', 'country', 'currency_preference',
        LastContactedFilter, LeadScoreFilter, 'created_at', 'assigned_to'
    )
    
    search_fields = (
        'name', 'email', 'phone', 'company', 'website', 'address_line1', 
        'city', 'notes', 'tags'
    )
    
    readonly_fields = (
        'client_id', 'total_orders', 'total_value', 'average_order_value', 
        'lifetime_value', 'lead_score', 'conversion_probability', 'last_order_date',
        'created_at', 'updated_at', 'days_since_last_contact_display',
        'full_address_display', 'tag_list_display'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'email', 'phone', 'company', 'website', 'industry', 'company_size'
            )
        }),
        ('Address', {
            'fields': (
                'address_line1', 'address_line2', 'city', 'province', 
                'postal_code', 'country', 'full_address_display'
            ),
            'classes': ('collapse',)
        }),
        ('Business Classification', {
            'fields': (
                'status', 'customer_type', 'priority', 'credit_limit', 
                'payment_terms', 'tax_number', 'currency_preference'
            )
        }),
        ('Analytics (Read Only)', {
            'fields': (
                'lead_score', 'conversion_probability', 'total_orders', 
                'total_value', 'average_order_value', 'lifetime_value', 'profit_margin'
            ),
            'classes': ('collapse',)
        }),
        ('Contact Tracking', {
            'fields': (
                'last_contacted', 'last_order_date', 'followup_date',
                'days_since_last_contact_display'
            ),
            'classes': ('collapse',)
        }),
        ('Team Assignment', {
            'fields': ('assigned_to', 'account_manager')
        }),
        ('Source & Attribution', {
            'fields': ('source', 'referral_source', 'marketing_campaign'),
            'classes': ('collapse',)
        }),
        ('Notes & Tags', {
            'fields': ('notes', 'internal_notes', 'tags', 'tag_list_display'),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('client_id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [InteractionInline, TaskInline]
    
    actions = [
        'mark_as_active_client', 'mark_as_prospect', 'mark_as_inactive',
        'assign_to_me', 'calculate_lead_scores', 'export_selected'
    ]
    
    list_per_page = 50
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('assigned_to', 'account_manager', 'created_by').annotate(
            interaction_count=Count('customerinteraction')
        )
    
    def status_badge(self, obj):
        color_map = {
            'lead': 'info',
            'prospect': 'warning', 
            'client': 'success',
            'inactive': 'secondary',
            'lost': 'danger'
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def customer_type_badge(self, obj):
        return format_html(
            '<span class="badge badge-light">{}</span>',
            obj.get_customer_type_display()
        )
    customer_type_badge.short_description = 'Type'
    customer_type_badge.admin_order_field = 'customer_type'
    
    def priority_badge(self, obj):
        color_map = {
            'low': 'light',
            'medium': 'secondary',
            'high': 'warning',
            'vip': 'danger'
        }
        color = color_map.get(obj.priority, 'light')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'
    
    def lead_score_badge(self, obj):
        score = obj.lead_score or 0
        if score >= 80:
            color = 'success'
        elif score >= 50:
            color = 'warning'
        else:
            color = 'danger'
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, f"{score}%"
        )
    lead_score_badge.short_description = 'Lead Score'
    lead_score_badge.admin_order_field = 'lead_score'
    
    def last_contacted_display(self, obj):
        if obj.last_contacted:
            days_ago = (timezone.now() - obj.last_contacted).days
            if days_ago == 0:
                return "Today"
            elif days_ago == 1:
                return "Yesterday"
            else:
                return f"{days_ago} days ago"
        return format_html('<span class="text-muted">Never</span>')
    last_contacted_display.short_description = 'Last Contact'
    last_contacted_display.admin_order_field = 'last_contacted'
    
    def total_interactions(self, obj):
        return obj.interaction_count if hasattr(obj, 'interaction_count') else 0
    total_interactions.short_description = 'Interactions'
    
    def total_value_display(self, obj):
        if obj.total_value > 0:
            return f"${obj.total_value:,.0f}"
        return "-"
    total_value_display.short_description = 'Total Value'
    total_value_display.admin_order_field = 'total_value'
    
    def days_since_last_contact_display(self, obj):
        days = obj.days_since_last_contact
        return f"{days} days" if days else "Never contacted"
    days_since_last_contact_display.short_description = 'Days Since Last Contact'
    
    def full_address_display(self, obj):
        return obj.full_address or "No address provided"
    full_address_display.short_description = 'Full Address'
    
    def tag_list_display(self, obj):
        tags = obj.tag_list
        if tags:
            return ", ".join(tags)
        return "No tags"
    tag_list_display.short_description = 'Tags'
    
    # Actions
    def mark_as_active_client(self, request, queryset):
        updated = queryset.update(status='client')
        self.message_user(request, f'{updated} clients marked as active.')
    mark_as_active_client.short_description = "Mark selected as active clients"
    
    def mark_as_prospect(self, request, queryset):
        updated = queryset.update(status='prospect')
        self.message_user(request, f'{updated} clients marked as prospects.')
    mark_as_prospect.short_description = "Mark selected as prospects"
    
    def mark_as_inactive(self, request, queryset):
        updated = queryset.update(status='inactive')
        self.message_user(request, f'{updated} clients marked as inactive.')
    mark_as_inactive.short_description = "Mark selected as inactive"
    
    def assign_to_me(self, request, queryset):
        updated = queryset.update(assigned_to=request.user)
        self.message_user(request, f'{updated} clients assigned to you.')
    assign_to_me.short_description = "Assign selected clients to me"
    
    def calculate_lead_scores(self, request, queryset):
        updated = 0
        for client in queryset:
            client.calculate_lead_score()
            updated += 1
        self.message_user(request, f'Lead scores calculated for {updated} clients.')
    calculate_lead_scores.short_description = "Recalculate lead scores"
    
    def export_selected(self, request, queryset):
        # This would implement CSV export
        self.message_user(request, "Export functionality will be implemented.")
    export_selected.short_description = "Export selected clients"


@admin.register(CustomerInteraction)
class CustomerInteractionAdmin(admin.ModelAdmin):
    list_display = (
        'client', 'interaction_type_badge', 'subject', 'outcome_badge', 
        'next_followup_display', 'created_by', 'created_at'
    )
    
    list_filter = (
        'interaction_type', 'outcome', 'created_at', 'next_followup', 'created_by'
    )
    
    search_fields = ('client__name', 'client__email', 'subject', 'notes')
    
    readonly_fields = ('created_at', 'updated_at', 'is_followup_due', 'is_followup_overdue')
    
    fieldsets = (
        ('Interaction Details', {
            'fields': ('client', 'interaction_type', 'subject', 'notes', 'outcome')
        }),
        ('Additional Info', {
            'fields': ('duration_minutes', 'participants', 'attachments'),
            'classes': ('collapse',)
        }),
        ('Follow-up', {
            'fields': ('next_followup', 'followup_notes', 'is_followup_due', 'is_followup_overdue')
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ('client',)
    autocomplete_fields = ('client',)
    
    list_per_page = 100
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    def interaction_type_badge(self, obj):
        return format_html(
            '<span class="badge badge-secondary">{}</span>',
            obj.get_interaction_type_display()
        )
    interaction_type_badge.short_description = 'Type'
    interaction_type_badge.admin_order_field = 'interaction_type'
    
    def outcome_badge(self, obj):
        if not obj.outcome:
            return "-"
        
        color_map = {
            'positive': 'success',
            'neutral': 'secondary',
            'negative': 'danger',
            'no_response': 'warning'
        }
        color = color_map.get(obj.outcome, 'secondary')
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_outcome_display()
        )
    outcome_badge.short_description = 'Outcome'
    outcome_badge.admin_order_field = 'outcome'
    
    def next_followup_display(self, obj):
        if obj.next_followup:
            if obj.is_followup_overdue:
                return format_html(
                    '<span class="text-danger">{} (Overdue)</span>',
                    obj.next_followup.strftime('%m/%d/%Y %H:%M')
                )
            elif obj.is_followup_due:
                return format_html(
                    '<span class="text-warning">{} (Due)</span>',
                    obj.next_followup.strftime('%m/%d/%Y %H:%M')
                )
            else:
                return obj.next_followup.strftime('%m/%d/%Y %H:%M')
        return "-"
    next_followup_display.short_description = 'Next Follow-up'
    next_followup_display.admin_order_field = 'next_followup'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New interaction
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'client', 'stage_badge', 'value_display', 'probability',
        'weighted_value_display', 'expected_close_date', 'assigned_to'
    )
    
    list_filter = ('stage', 'priority', 'currency', 'assigned_to', 'created_at')
    
    search_fields = ('title', 'client__name', 'description')
    
    readonly_fields = (
        'deal_id', 'weighted_value', 'days_until_close', 'is_overdue',
        'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Deal Information', {
            'fields': ('title', 'client', 'description', 'value', 'currency')
        }),
        ('Sales Process', {
            'fields': ('stage', 'probability', 'priority', 'weighted_value')
        }),
        ('Timeline', {
            'fields': ('expected_close_date', 'actual_close_date', 'days_until_close', 'is_overdue')
        }),
        ('Assignment & Source', {
            'fields': ('assigned_to', 'source', 'competitor'),
            'classes': ('collapse',)
        }),
        ('Closure Info', {
            'fields': ('loss_reason',),
            'classes': ('collapse',)
        }),
        ('System Info', {
            'fields': ('deal_id', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ('client',)
    autocomplete_fields = ('client',)
    
    list_per_page = 50
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    def stage_badge(self, obj):
        color_map = {
            'prospecting': 'info',
            'qualification': 'primary',
            'proposal': 'warning',
            'negotiation': 'secondary',
            'closed_won': 'success',
            'closed_lost': 'danger'
        }
        color = color_map.get(obj.stage, 'secondary')
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_stage_display()
        )
    stage_badge.short_description = 'Stage'
    stage_badge.admin_order_field = 'stage'
    
    def value_display(self, obj):
        return f"${obj.value:,.0f} {obj.currency}"
    value_display.short_description = 'Value'
    value_display.admin_order_field = 'value'
    
    def weighted_value_display(self, obj):
        return f"${obj.weighted_value:,.0f}"
    weighted_value_display.short_description = 'Weighted Value'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New deal
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'client', 'deal', 'priority_badge', 'status_badge',
        'due_date_display', 'assigned_to', 'created_at'
    )
    
    list_filter = ('priority', 'status', 'due_date', 'assigned_to', 'created_at')
    
    search_fields = ('title', 'description', 'client__name')
    
    readonly_fields = (
        'is_overdue', 'days_until_due', 'completed_at', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Task Details', {
            'fields': ('title', 'description', 'client', 'deal')
        }),
        ('Status & Priority', {
            'fields': ('priority', 'status', 'assigned_to')
        }),
        ('Timeline', {
            'fields': ('due_date', 'completed_at', 'days_until_due', 'is_overdue')
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ('client', 'deal')
    autocomplete_fields = ('client', 'deal')
    
    list_per_page = 100
    date_hierarchy = 'created_at'
    ordering = ('due_date', '-priority')
    
    def priority_badge(self, obj):
        color_map = {
            'low': 'light',
            'medium': 'secondary',
            'high': 'warning',
            'urgent': 'danger'
        }
        color = color_map.get(obj.priority, 'secondary')
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'
    
    def status_badge(self, obj):
        color_map = {
            'pending': 'secondary',
            'in_progress': 'primary',
            'completed': 'success',
            'cancelled': 'danger'
        }
        color = color_map.get(obj.status, 'secondary')
        
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def due_date_display(self, obj):
        if obj.due_date:
            if obj.is_overdue:
                return format_html(
                    '<span class="text-danger">{} (Overdue)</span>',
                    obj.due_date.strftime('%m/%d/%Y %H:%M')
                )
            else:
                return obj.due_date.strftime('%m/%d/%Y %H:%M')
        return "-"
    due_date_display.short_description = 'Due Date'
    due_date_display.admin_order_field = 'due_date'
    
    def save_model(self, request, obj, form, change):
        if not change:  # New task
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ClientNote)
class ClientNoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'client', 'is_private', 'created_by', 'created_at')
    list_filter = ('is_private', 'created_at', 'created_by')
    search_fields = ('title', 'content', 'client__name')
    
    fieldsets = (
        ('Note Details', {
            'fields': ('client', 'title', 'content', 'attachment')
        }),
        ('Privacy', {
            'fields': ('is_private',)
        }),
        ('System Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    raw_id_fields = ('client',)
    autocomplete_fields = ('client',)
    
    def save_model(self, request, obj, form, change):
        if not change:  # New note
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CRMSettings)
class CRMSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Lead Management', {
            'fields': ('lead_scoring_enabled', 'auto_assign_leads')
        }),
        ('Follow-up Settings', {
            'fields': ('default_followup_days', 'followup_reminder_hours')
        }),
        ('Data & Analytics', {
            'fields': ('analytics_retention_days',)
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'overdue_followup_alerts')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one settings instance
        return not CRMSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion of settings
        return False


# Admin site customization
admin.site.site_header = "BlitzTech CRM Administration"
admin.site.site_title = "CRM Admin"
admin.site.index_title = "CRM Management"
