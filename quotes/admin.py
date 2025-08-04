# quotes/admin.py
"""
Django Admin Interface for Quote Management

This admin interface provides a comprehensive management system for quotes,
allowing administrators to view, edit, and manage all aspects of the quote system.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal

from .models import Quote, QuoteItem, QuoteRevision, QuoteTemplate

class QuoteItemInline(admin.TabularInline):
    """Inline editing of quote items within quote admin"""
    model = QuoteItem
    extra = 0
    fields = [
        'description', 'quantity', 'unit_price', 'total_price', 
        'source_type', 'supplier'
    ]
    readonly_fields = ['total_price']

@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    """
    Comprehensive admin interface for Quote management.
    Provides filtering, search, and bulk actions for efficient quote management.
    """
    
    list_display = [
        'quote_number', 'client_name', 'title', 'status_badge', 
        'total_amount_display', 'currency', 'created_at', 'validity_date', 
        'assigned_to', 'actions_column'
    ]
    
    list_filter = [
        'status', 'priority', 'currency', 'created_at', 'validity_date',
        'assigned_to', 'created_by'
    ]
    
    search_fields = [
        'quote_number', 'title', 'description', 'client__name', 
        'client__company', 'client__email'
    ]
    
    readonly_fields = [
        'quote_id', 'quote_number', 'subtotal', 'tax_amount', 
        'discount_amount', 'total_amount', 'created_at', 'updated_at',
        'sent_date', 'viewed_date', 'response_date'
    ]
    
    fieldsets = (
        ('Quote Information', {
            'fields': (
                'quote_id', 'quote_number', 'client', 'title', 'description'
            )
        }),
        ('Status & Assignment', {
            'fields': (
                'status', 'priority', 'assigned_to', 'created_by', 'approved_by'
            )
        }),
        ('Financial Details', {
            'fields': (
                ('subtotal', 'discount_percentage', 'discount_amount'),
                ('tax_rate', 'tax_amount', 'total_amount', 'currency')
            )
        }),
        ('Terms & Conditions', {
            'fields': (
                'payment_terms', 'delivery_terms', 'validity_date'
            )
        }),
        ('Tracking Information', {
            'fields': (
                'created_at', 'updated_at', 'sent_date', 
                'viewed_date', 'response_date'
            ),
            'classes': ('collapse',)
        }),
        ('Internal Notes', {
            'fields': ('internal_notes',),
            'classes': ('collapse',)
        })
    )
    
    inlines = [QuoteItemInline]  # Fixed: Reference the class, not string
    
    actions = [
        'mark_as_sent', 'mark_as_accepted', 'mark_as_rejected', 
        'recalculate_totals', 'export_to_excel'
    ]
    
    def client_name(self, obj):
        """Display client name with link to client admin"""
        if obj.client:
            url = reverse('admin:crm_client_change', args=[obj.client.pk])
            return format_html('<a href="{}">{}</a>', url, obj.client.name)
        return '-'
    client_name.short_description = 'Client'
    client_name.admin_order_field = 'client__name'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'draft': '#ffc107',
            'sent': '#0d6efd',
            'viewed': '#17a2b8',
            'under_review': '#fd7e14',
            'accepted': '#198754',
            'rejected': '#dc3545',
            'expired': '#6c757d',
            'converted': '#20c997',
            'cancelled': '#6c757d'
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background: {}; padding: 3px 8px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def total_amount_display(self, obj):
        """Display formatted total amount"""
        return f"${obj.total_amount:,.2f}"
    total_amount_display.short_description = 'Total'
    total_amount_display.admin_order_field = 'total_amount'
    
    def actions_column(self, obj):
        """Display action buttons for quick access"""
        actions = []
        
        # View detail link
        detail_url = reverse('quotes:quote_detail', args=[obj.id])
        actions.append(f'<a href="{detail_url}" target="_blank" title="View Details">👁️</a>')
        
        # Edit in builder if editable
        if obj.status in ['draft', 'sent']:
            builder_url = reverse('quotes:quote_builder', args=[obj.id])
            actions.append(f'<a href="{builder_url}" target="_blank" title="Edit in Builder">✏️</a>')
        
        # Generate PDF
        pdf_url = reverse('quotes:generate_quote_pdf', args=[obj.id])
        actions.append(f'<a href="{pdf_url}" target="_blank" title="Download PDF">📄</a>')
        
        return mark_safe(' '.join(actions))
    actions_column.short_description = 'Actions'
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related(
            'client', 'assigned_to', 'created_by', 'approved_by'
        ).prefetch_related('items')
    
    # Admin Actions
    def mark_as_sent(self, request, queryset):
        """Mark selected quotes as sent"""
        updated = queryset.filter(status='draft').update(
            status='sent', 
            sent_date=timezone.now()
        )
        self.message_user(request, f'{updated} quotes marked as sent.')
    mark_as_sent.short_description = "Mark selected quotes as sent"
    
    def mark_as_accepted(self, request, queryset):
        """Mark selected quotes as accepted"""
        updated = queryset.filter(
            status__in=['sent', 'viewed', 'under_review']
        ).update(
            status='accepted', 
            response_date=timezone.now()
        )
        self.message_user(request, f'{updated} quotes marked as accepted.')
    mark_as_accepted.short_description = "Mark selected quotes as accepted"
    
    def mark_as_rejected(self, request, queryset):
        """Mark selected quotes as rejected"""
        updated = queryset.filter(
            status__in=['sent', 'viewed', 'under_review']
        ).update(
            status='rejected', 
            response_date=timezone.now()
        )
        self.message_user(request, f'{updated} quotes marked as rejected.')
    mark_as_rejected.short_description = "Mark selected quotes as rejected"
    
    def recalculate_totals(self, request, queryset):
        """Recalculate totals for selected quotes"""
        count = 0
        for quote in queryset:
            quote.calculate_totals()
            count += 1
        self.message_user(request, f'Totals recalculated for {count} quotes.')
    recalculate_totals.short_description = "Recalculate totals for selected quotes"

@admin.register(QuoteItem)
class QuoteItemAdmin(admin.ModelAdmin):
    """Admin interface for individual quote items"""
    
    list_display = [
        'quote_link', 'description', 'quantity', 'unit_price_display', 
        'total_price_display', 'source_type', 'supplier'
    ]
    
    list_filter = ['source_type', 'supplier', 'quote__status']
    
    search_fields = [
        'description', 'quote__quote_number', 'product__name', 
        'product__sku'
    ]
    
    def quote_link(self, obj):
        """Link to parent quote"""
        url = reverse('admin:quotes_quote_change', args=[obj.quote.pk])
        return format_html('<a href="{}">{}</a>', url, obj.quote.quote_number)
    quote_link.short_description = 'Quote'
    
    def unit_price_display(self, obj):
        return f"${obj.unit_price:,.2f}"
    unit_price_display.short_description = 'Unit Price'
    
    def total_price_display(self, obj):
        return f"${obj.total_price:,.2f}"
    total_price_display.short_description = 'Total Price'

@admin.register(QuoteRevision)
class QuoteRevisionAdmin(admin.ModelAdmin):
    """Admin interface for quote revision history"""
    
    list_display = [
        'quote_link', 'revision_number', 'change_summary', 
        'previous_total', 'new_total', 'created_by', 'created_at'
    ]
    
    list_filter = ['created_at', 'created_by']
    
    search_fields = ['quote__quote_number', 'change_summary']
    
    readonly_fields = ['created_at']
    
    def quote_link(self, obj):
        """Link to parent quote"""
        url = reverse('admin:quotes_quote_change', args=[obj.quote.pk])
        return format_html('<a href="{}">{}</a>', url, obj.quote.quote_number)
    quote_link.short_description = 'Quote'

@admin.register(QuoteTemplate)
class QuoteTemplateAdmin(admin.ModelAdmin):
    """Admin interface for quote templates"""
    
    list_display = [
        'name', 'description', 'is_active', 'default_validity_days', 
        'created_by', 'created_at'
    ]
    
    list_filter = ['is_active', 'created_at', 'created_by']
    
    search_fields = ['name', 'description']
    
    readonly_fields = ['created_at']
    