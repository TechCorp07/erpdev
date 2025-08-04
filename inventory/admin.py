# inventory/admin.py - Comprehensive Inventory Management Admin Interface

"""
Django Admin Configuration for Inventory Management

This admin interface provides comprehensive inventory management capabilities
for your team. It's designed to be powerful yet user-friendly, with bulk
operations, advanced filtering, and intelligent defaults that make inventory
management efficient and error-free.

Key Features:
- Bulk stock adjustments and updates
- Advanced search and filtering
- Real-time stock level monitoring
- Automatic reorder alerts
- Purchase order management
- Stock movement tracking
- Supplier performance analytics
"""

from django.contrib import admin
from django.db import transaction, models
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from decimal import Decimal
import csv
from django.http import HttpResponse

from .models import (
    Category, Supplier, Location, Product, StockLevel, StockMovement,
    StockTake, StockTakeItem, PurchaseOrder, PurchaseOrderItem, ReorderAlert
)


# =====================================
# ENHANCED ADMIN MIXINS AND UTILITIES
# =====================================

class InventoryAdminMixin:
    """
    Base mixin for inventory admin classes with common functionality.
    
    This mixin provides consistent behavior across all inventory admin
    interfaces, including permission checks, bulk operations, and
    integration with your existing core system.
    """
    
    def get_queryset(self, request):
        """Optimize queries with select_related and prefetch_related"""
        qs = super().get_queryset(request)
        if hasattr(self.model, 'created_by'):
            qs = qs.select_related('created_by')
        return qs
    
    def save_model(self, request, obj, form, change):
        """Auto-set created_by for new objects"""
        if not change and hasattr(obj, 'created_by'):
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        """Check inventory permissions"""
        return request.user.has_perm('inventory.add_' + self.model._meta.model_name)
    
    def has_change_permission(self, request, obj=None):
        """Check inventory permissions"""
        return request.user.has_perm('inventory.change_' + self.model._meta.model_name)


# =====================================
# CATEGORY MANAGEMENT
# =====================================

@admin.register(Category)
class CategoryAdmin(InventoryAdminMixin, admin.ModelAdmin):
    """
    Category management with hierarchical display and bulk operations.
    
    Categories are the foundation of your product organization. This interface
    makes it easy to create logical product hierarchies and set default
    business rules for entire product categories.
    """
    
    list_display = (
        'name', 'parent', 'get_product_count', 'default_markup_percentage',
        'default_reorder_level', 'get_total_value', 'is_active', 'created_at'
    )
    
    list_filter = (
        'is_active', 'parent', 'created_at', 'default_markup_percentage'
    )
    
    search_fields = ('name', 'description')
    
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'parent', 'description')
        }),
        ('Business Rules', {
            'fields': (
                'default_markup_percentage', 
                'default_reorder_level'
            ),
            'description': 'Default settings for products in this category'
        }),
        ('Display & Status', {
            'fields': ('display_order', 'is_active')
        })
    )
    
    ordering = ['display_order', 'name']
    
    actions = [
        'apply_markup_to_products',
        'update_reorder_levels',
        'export_category_report'
    ]
    
    def get_product_count(self, obj):
        """Display number of products in category"""
        count = obj.get_product_count()
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return '0 products'
    get_product_count.short_description = 'Products'
    
    def get_total_value(self, obj):
        """Display total stock value for category"""
        value = obj.get_total_stock_value()
        return f"${value:,.2f}" if value else "$0.00"
    get_total_value.short_description = 'Stock Value'
    
    @admin.action(description='Apply markup percentage to all products in selected categories')
    def apply_markup_to_products(self, request, queryset):
        """Bulk apply category markup to all products"""
        if 'apply' in request.POST:
            updated_count = 0
            for category in queryset:
                products = Product.objects.filter(category=category)
                for product in products:
                    new_price = product.cost_price * (1 + category.default_markup_percentage / 100)
                    product.selling_price = new_price
                    product.save(update_fields=['selling_price'])
                    updated_count += 1
            
            messages.success(request, f'Updated selling prices for {updated_count} products.')
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/inventory/apply_markup_confirmation.html', {
            'categories': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })
    
    @admin.action(description='Update reorder levels for products in selected categories')
    def update_reorder_levels(self, request, queryset):
        """Bulk update reorder levels based on category defaults"""
        updated_count = 0
        for category in queryset:
            updated = Product.objects.filter(category=category).update(
                reorder_level=category.default_reorder_level
            )
            updated_count += updated
        
        messages.success(request, f'Updated reorder levels for {updated_count} products.')


# =====================================
# SUPPLIER MANAGEMENT
# =====================================

@admin.register(Supplier)
class SupplierAdmin(InventoryAdminMixin, admin.ModelAdmin):
    """
    Comprehensive supplier management with performance tracking.
    
    Suppliers are critical business partners. This interface helps you
    manage all aspects of supplier relationships, from basic contact
    information to performance analytics and payment terms.
    """
    
    list_display = (
        'name', 'supplier_code', 'supplier_type', 'country', 'currency',
        'get_product_count', 'average_lead_time_days', 'reliability_rating',
        'is_preferred', 'is_active'
    )
    
    list_filter = (
        'supplier_type', 'country', 'currency', 'is_active', 
        'is_preferred', 'reliability_rating'
    )
    
    search_fields = (
        'name', 'supplier_code', 'contact_person', 'email', 'city'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'supplier_code', 'supplier_type', 'contact_person'
            )
        }),
        ('Contact Details', {
            'fields': (
                'email', 'phone', 'website',
                ('address_line_1', 'address_line_2'),
                ('city', 'state_province', 'postal_code'),
                'country'
            )
        }),
        ('Business Terms', {
            'fields': (
                'payment_terms', 'currency', 'minimum_order_amount',
                'requires_purchase_order'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'average_lead_time_days', 'reliability_rating'
            )
        }),
        ('Status & Preferences', {
            'fields': (
                ('is_active', 'is_preferred'),
                'tax_number'
            )
        }),
        ('Additional Information', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )
    
    ordering = ['name']
    
    actions = [
        'mark_as_preferred',
        'update_lead_times',
        'export_supplier_report',
        'send_supplier_performance_report'
    ]
    
    def get_product_count(self, obj):
        """Display number of products from this supplier"""
        count = obj.total_products
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?supplier__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return '0 products'
    get_product_count.short_description = 'Products'
    
    @admin.action(description='Mark selected suppliers as preferred')
    def mark_as_preferred(self, request, queryset):
        """Mark suppliers as preferred for priority in sourcing"""
        updated = queryset.update(is_preferred=True)
        messages.success(request, f'Marked {updated} suppliers as preferred.')
    
    @admin.action(description='Export supplier performance report')
    def export_supplier_report(self, request, queryset):
        """Export detailed supplier performance data"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="supplier_report.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Supplier Code', 'Name', 'Type', 'Country', 'Products',
            'Lead Time (Days)', 'Reliability Rating', 'Currency',
            'Payment Terms', 'Is Preferred', 'Is Active'
        ])
        
        for supplier in queryset:
            writer.writerow([
                supplier.supplier_code,
                supplier.name,
                supplier.get_supplier_type_display(),
                supplier.country,
                supplier.total_products,
                supplier.average_lead_time_days,
                supplier.reliability_rating,
                supplier.currency,
                supplier.payment_terms,
                'Yes' if supplier.is_preferred else 'No',
                'Yes' if supplier.is_active else 'No'
            ])
        
        return response


# =====================================
# LOCATION MANAGEMENT
# =====================================

@admin.register(Location)
class LocationAdmin(InventoryAdminMixin, admin.ModelAdmin):
    """
    Multi-location inventory management interface.
    
    Locations represent different storage areas in your business.
    This interface helps you manage warehouse space, shop floor inventory,
    and track capacity utilization across all your locations.
    """
    
    list_display = (
        'name', 'location_code', 'location_type', 'get_capacity_usage',
        'get_stock_value', 'is_sellable', 'is_default', 'is_active'
    )
    
    list_filter = (
        'location_type', 'is_active', 'is_sellable', 'is_default'
    )
    
    search_fields = ('name', 'location_code', 'contact_person')
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'name', 'location_code', 'location_type', 'address'
            )
        }),
        ('Contact Details', {
            'fields': ('contact_person', 'phone')
        }),
        ('Operational Settings', {
            'fields': (
                ('is_active', 'is_sellable', 'is_default'),
                'max_capacity'
            )
        })
    )
    
    actions = ['set_as_default', 'export_location_report']
    
    def get_capacity_usage(self, obj):
        """Display capacity usage with color coding"""
        usage = obj.current_capacity_usage
        if usage > 90:
            color = 'red'
        elif usage > 75:
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, usage
        )
    get_capacity_usage.short_description = 'Capacity Usage'
    
    def get_stock_value(self, obj):
        """Display total stock value at location"""
        value = obj.total_stock_value
        return f"${value:,.2f}"
    get_stock_value.short_description = 'Stock Value'
    
    @admin.action(description='Set selected location as default')
    def set_as_default(self, request, queryset):
        """Set a location as the default for new stock receipts"""
        if queryset.count() > 1:
            messages.error(request, 'Please select only one location to set as default.')
            return
        
        # Clear existing default
        Location.objects.update(is_default=False)
        
        # Set new default
        location = queryset.first()
        location.is_default = True
        location.save()
        
        messages.success(request, f'{location.name} is now the default location.')


# =====================================
# PRODUCT MANAGEMENT - THE CORE INTERFACE
# =====================================

class StockLevelInline(admin.TabularInline):
    """Inline editor for stock levels at different locations"""
    model = StockLevel
    extra = 0
    readonly_fields = ('last_movement',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('location')


@admin.register(Product)
class ProductAdmin(InventoryAdminMixin, admin.ModelAdmin):
    """
    Comprehensive product management interface.
    
    This is the heart of your inventory system. Every aspect of product
    management is handled here - from basic product information to complex
    pricing strategies, stock control, and performance analytics.
    
    The interface is designed to minimize data entry while maximizing
    business intelligence and operational efficiency.
    """
    
    list_display = (
        'sku', 'name', 'category', 'supplier', 'get_stock_status',
        'current_stock', 'available_stock', 'get_profit_margin',
        'selling_price', 'get_stock_value', 'is_active'
    )
    
    list_filter = (
        'category', 'supplier', 'is_active', 'product_type',
        'is_serialized', 'requires_quality_check',
        ('created_at', admin.DateFieldListFilter)
    )
    
    search_fields = (
        'sku', 'name', 'barcode', 'manufacturer_part_number',
        'supplier_sku', 'brand', 'model_number'
    )
    
    readonly_fields = (
        'available_stock', 'profit_margin_percentage', 'profit_amount',
        'stock_value', 'stock_status', 'needs_reorder',
        'total_sold', 'total_revenue', 'last_sold_date', 'last_restocked_date'
    )
    
    fieldsets = (
        ('Product Identification', {
            'fields': (
                ('sku', 'barcode'),
                'name',
                'short_description',
                'description'
            )
        }),
        ('Categorization', {
            'fields': (
                ('category', 'supplier'),
                ('product_type', 'brand'),
                ('model_number', 'manufacturer_part_number', 'supplier_sku')
            )
        }),
        ('Physical Attributes', {
            'fields': (
                ('weight', 'dimensions')
            ),
            'classes': ('collapse',)
        }),
        ('Pricing & Costing', {
            'fields': (
                ('cost_price', 'selling_price', 'currency'),
                ('profit_margin_percentage', 'profit_amount')
            )
        }),
        ('Stock Management', {
            'fields': (
                ('current_stock', 'reserved_stock', 'available_stock'),
                ('reorder_level', 'reorder_quantity', 'max_stock_level'),
                ('stock_status', 'stock_value', 'needs_reorder')
            )
        }),
        ('Supplier Information', {
            'fields': (
                ('supplier_lead_time_days', 'minimum_order_quantity')
            )
        }),
        ('Product Flags', {
            'fields': (
                ('is_active', 'is_serialized'),
                ('is_perishable', 'requires_quality_check')
            )
        }),
        ('Performance Analytics', {
            'fields': (
                ('total_sold', 'total_revenue'),
                ('last_sold_date', 'last_restocked_date')
            ),
            'classes': ('collapse',)
        }),
        ('SEO & Marketing', {
            'fields': (
                'meta_title',
                'meta_description'
            ),
            'classes': ('collapse',)
        })
    )
    
    inlines = [StockLevelInline]
    
    ordering = ['name']
    
    actions = [
        'bulk_adjust_stock',
        'apply_markup_percentage',
        'mark_for_reorder',
        'update_cost_prices',
        'export_product_catalog',
        'generate_barcode_labels',
        'check_stock_levels'
    ]
    
    def get_stock_status(self, obj):
        """Display stock status with color coding"""
        status = obj.stock_status
        colors = {
            'in_stock': 'green',
            'low_stock': 'orange', 
            'out_of_stock': 'red',
            'discontinued': 'gray'
        }
        
        color = colors.get(status, 'black')
        display_text = obj.get_stock_status_display() if hasattr(obj, 'get_stock_status_display') else status.replace('_', ' ').title()
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, display_text
        )
    get_stock_status.short_description = 'Stock Status'
    
    def get_profit_margin(self, obj):
        """Display profit margin with color coding"""
        margin = obj.profit_margin_percentage
        if margin < 10:
            color = 'red'
        elif margin < 25:
            color = 'orange'
        else:
            color = 'green'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, margin
        )
    get_profit_margin.short_description = 'Profit Margin'
    
    def get_stock_value(self, obj):
        """Display current stock value"""
        value = obj.stock_value
        return f"${value:,.2f}"
    get_stock_value.short_description = 'Stock Value'
    
    @admin.action(description='Bulk adjust stock levels for selected products')
    def bulk_adjust_stock(self, request, queryset):
        """Bulk stock adjustment interface"""
        if 'apply' in request.POST:
            adjustment_type = request.POST.get('adjustment_type')
            adjustment_value = int(request.POST.get('adjustment_value', 0))
            reason = request.POST.get('reason', 'Bulk admin adjustment')
            
            updated_count = 0
            
            with transaction.atomic():
                for product in queryset:
                    if adjustment_type == 'set':
                        product.adjust_stock(
                            adjustment_value - product.current_stock,
                            reason,
                            request.user
                        )
                    elif adjustment_type == 'add':
                        product.adjust_stock(adjustment_value, reason, request.user)
                    elif adjustment_type == 'subtract':
                        product.adjust_stock(-adjustment_value, reason, request.user)
                    
                    updated_count += 1
            
            messages.success(request, f'Stock adjusted for {updated_count} products.')
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/inventory/bulk_stock_adjustment.html', {
            'products': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })
    
    @admin.action(description='Apply markup percentage to selected products')
    def apply_markup_percentage(self, request, queryset):
        """Apply consistent markup percentage to products"""
        if 'apply' in request.POST:
            markup_percentage = float(request.POST.get('markup_percentage', 0))
            
            updated_count = 0
            with transaction.atomic():
                for product in queryset:
                    new_price = product.cost_price * (1 + markup_percentage / 100)
                    product.selling_price = new_price
                    product.save(update_fields=['selling_price'])
                    updated_count += 1
            
            messages.success(request, f'Applied {markup_percentage}% markup to {updated_count} products.')
            return HttpResponseRedirect(request.get_full_path())
        
        return render(request, 'admin/inventory/apply_markup.html', {
            'products': queryset,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        })
    
    @admin.action(description='Mark selected products for reordering')
    def mark_for_reorder(self, request, queryset):
        """Create reorder alerts for selected products"""
        created_count = 0
        
        for product in queryset.filter(is_active=True):
            if product.needs_reorder:
                alert, created = ReorderAlert.objects.get_or_create(
                    product=product,
                    status='active',
                    defaults={
                        'priority': 'medium',
                        'current_stock': product.current_stock,
                        'reorder_level': product.reorder_level,
                        'suggested_order_quantity': product.reorder_quantity,
                        'suggested_supplier': product.supplier,
                        'estimated_cost': product.reorder_quantity * product.cost_price
                    }
                )
                if created:
                    created_count += 1
        
        messages.success(request, f'Created reorder alerts for {created_count} products.')
    
    @admin.action(description='Export product catalog')
    def export_product_catalog(self, request, queryset):
        """Export comprehensive product catalog"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="product_catalog.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'SKU', 'Name', 'Category', 'Supplier', 'Cost Price', 'Selling Price',
            'Profit Margin %', 'Current Stock', 'Available Stock', 'Reorder Level',
            'Stock Status', 'Last Restocked', 'Is Active'
        ])
        
        for product in queryset:
            writer.writerow([
                product.sku,
                product.name,
                product.category.name,
                product.supplier.name,
                product.cost_price,
                product.selling_price,
                product.profit_margin_percentage,
                product.current_stock,
                product.available_stock,
                product.reorder_level,
                product.stock_status,
                product.last_restocked_date.strftime('%Y-%m-%d') if product.last_restocked_date else '',
                'Yes' if product.is_active else 'No'
            ])
        
        return response


# =====================================
# STOCK MOVEMENT TRACKING
# =====================================

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """
    Complete audit trail of stock movements.
    
    This interface provides full visibility into every stock change
    in your system. It's essential for compliance, theft detection,
    and understanding inventory flow patterns.
    """
    
    list_display = (
        'created_at', 'product', 'movement_type', 'quantity',
        'from_location', 'to_location', 'reference', 'created_by'
    )
    
    list_filter = (
        'movement_type', 'created_at', 'from_location', 'to_location'
    )
    
    search_fields = (
        'product__sku', 'product__name', 'reference', 'notes'
    )
    
    readonly_fields = (
        'product', 'movement_type', 'quantity', 'from_location', 'to_location',
        'previous_stock', 'new_stock', 'reference', 'notes', 'unit_cost',
        'total_cost', 'created_at', 'created_by'
    )
    
    date_hierarchy = 'created_at'
    
    ordering = ['-created_at']
    
    def has_add_permission(self, request):
        """Prevent manual addition of stock movements"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Stock movements are read-only after creation"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of stock movements for audit trail"""
        return request.user.is_superuser


# =====================================
# PURCHASE ORDER MANAGEMENT
# =====================================

class PurchaseOrderItemInline(admin.TabularInline):
    """Inline editor for purchase order items"""
    model = PurchaseOrderItem
    extra = 1
    readonly_fields = ('total_price', 'quantity_outstanding')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(InventoryAdminMixin, admin.ModelAdmin):
    """
    Purchase order management with supplier integration.
    
    This interface manages the complete purchase-to-receipt workflow.
    From generating orders based on reorder alerts to tracking deliveries
    and updating stock levels automatically.
    """
    
    list_display = (
        'po_number', 'supplier', 'status', 'order_date',
        'expected_delivery_date', 'total_amount', 'currency',
        'get_items_count', 'is_overdue'
    )
    
    list_filter = (
        'status', 'currency', 'supplier',
        ('order_date', admin.DateFieldListFilter),
        ('expected_delivery_date', admin.DateFieldListFilter)
    )
    
    search_fields = (
        'po_number', 'supplier__name', 'delivery_instructions'
    )
    
    readonly_fields = ('subtotal', 'total_amount', 'is_overdue')
    
    fieldsets = (
        ('Purchase Order Details', {
            'fields': (
                'po_number', 'supplier', 'status'
            )
        }),
        ('Delivery Information', {
            'fields': (
                'delivery_location', 'expected_delivery_date',
                'actual_delivery_date', 'delivery_instructions'
            )
        }),
        ('Financial Details', {
            'fields': (
                ('subtotal', 'tax_amount', 'shipping_cost'),
                ('total_amount', 'currency')
            )
        }),
        ('Terms & Conditions', {
            'fields': ('payment_terms', 'notes')
        })
    )
    
    inlines = [PurchaseOrderItemInline]
    
    ordering = ['-order_date']
    
    actions = ['mark_as_received', 'export_po_report']
    
    def get_items_count(self, obj):
        """Display number of line items"""
        count = obj.items.count()
        return f"{count} item{'s' if count != 1 else ''}"
    get_items_count.short_description = 'Items'
    
    def save_related(self, request, form, formsets, change):
        """Recalculate totals when items change"""
        super().save_related(request, form, formsets, change)
        if formsets:
            form.instance.calculate_totals()
    
    @admin.action(description='Mark selected POs as received')
    def mark_as_received(self, request, queryset):
        """Bulk mark purchase orders as received"""
        updated = queryset.filter(status__in=['sent', 'acknowledged']).update(
            status='received',
            actual_delivery_date=timezone.now().date()
        )
        messages.success(request, f'Marked {updated} purchase orders as received.')


# =====================================
# REORDER ALERT MANAGEMENT
# =====================================

@admin.register(ReorderAlert)
class ReorderAlertAdmin(admin.ModelAdmin):
    """
    Reorder alert management and purchase order generation.
    
    This interface helps you manage automatic reorder alerts and
    convert them into purchase orders efficiently. It's your early
    warning system for stock shortages.
    """
    
    list_display = (
        'product', 'priority', 'status', 'current_stock', 'reorder_level',
        'suggested_order_quantity', 'suggested_supplier', 'estimated_cost',
        'created_at'
    )
    
    list_filter = (
        'priority', 'status', 'suggested_supplier',
        ('created_at', admin.DateFieldListFilter)
    )
    
    search_fields = (
        'product__sku', 'product__name', 'suggested_supplier__name'
    )
    
    readonly_fields = (
        'product', 'current_stock', 'reorder_level', 'estimated_stockout_date',
        'estimated_cost', 'created_at'
    )
    
    ordering = ['priority', '-created_at']
    
    actions = [
        'acknowledge_alerts',
        'create_purchase_orders',
        'update_priority'
    ]
    
    @admin.action(description='Acknowledge selected alerts')
    def acknowledge_alerts(self, request, queryset):
        """Bulk acknowledge reorder alerts"""
        updated = queryset.filter(status='active').update(
            status='acknowledged',
            acknowledged_by=request.user,
            acknowledged_at=timezone.now()
        )
        messages.success(request, f'Acknowledged {updated} reorder alerts.')
    
    @admin.action(description='Create purchase orders from selected alerts')
    def create_purchase_orders(self, request, queryset):
        """Generate purchase orders from reorder alerts"""
        # Group alerts by supplier
        alerts_by_supplier = {}
        for alert in queryset.filter(status__in=['active', 'acknowledged']):
            supplier = alert.suggested_supplier
            if supplier not in alerts_by_supplier:
                alerts_by_supplier[supplier] = []
            alerts_by_supplier[supplier].append(alert)
        
        created_pos = 0
        
        with transaction.atomic():
            for supplier, alerts in alerts_by_supplier.items():
                # Create PO
                po = PurchaseOrder.objects.create(
                    po_number=f"PO-{timezone.now().strftime('%Y%m%d')}-{supplier.supplier_code}",
                    supplier=supplier,
                    expected_delivery_date=timezone.now().date() + timezone.timedelta(
                        days=supplier.average_lead_time_days
                    ),
                    payment_terms=supplier.payment_terms,
                    currency=supplier.currency,
                    delivery_location=Location.objects.filter(is_default=True).first(),
                    created_by=request.user
                )
                
                # Add items
                for alert in alerts:
                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        product=alert.product,
                        quantity_ordered=alert.suggested_order_quantity,
                        unit_price=alert.product.cost_price
                    )
                    
                    # Mark alert as ordered
                    alert.status = 'ordered'
                    alert.purchase_order = po
                    alert.save()
                
                po.calculate_totals()
                created_pos += 1
        
        messages.success(request, f'Created {created_pos} purchase orders from reorder alerts.')


# =====================================
# STOCK TAKE MANAGEMENT
# =====================================

class StockTakeItemInline(admin.TabularInline):
    """Inline editor for stock take items"""
    model = StockTakeItem
    extra = 0
    readonly_fields = ('variance', 'variance_value')


@admin.register(StockTake)
class StockTakeAdmin(InventoryAdminMixin, admin.ModelAdmin):
    """
    Stock take management for physical inventory reconciliation.
    
    This interface manages the complete stock take process from planning
    to execution and variance resolution. Essential for maintaining
    accurate inventory records and identifying discrepancies.
    """
    
    list_display = (
        'reference', 'description', 'location', 'status',
        'scheduled_date', 'items_counted', 'variances_found',
        'total_adjustment_value', 'created_by'
    )
    
    list_filter = (
        'status', 'location',
        ('scheduled_date', admin.DateFieldListFilter),
        ('completed_at', admin.DateFieldListFilter)
    )
    
    search_fields = ('reference', 'description', 'notes')
    
    readonly_fields = (
        'items_counted', 'variances_found', 'total_adjustment_value',
        'started_at', 'completed_at'
    )
    
    fieldsets = (
        ('Stock Take Details', {
            'fields': (
                'reference', 'description', 'location', 'status'
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_date', 'started_at', 'completed_at'
            )
        }),
        ('Results Summary', {
            'fields': (
                'items_counted', 'variances_found', 'total_adjustment_value'
            )
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        })
    )
    
    inlines = [StockTakeItemInline]
    
    ordering = ['-scheduled_date']
    
    actions = ['start_stock_take', 'complete_stock_take']
    
    @admin.action(description='Start selected stock takes')
    def start_stock_take(self, request, queryset):
        """Mark stock takes as in progress"""
        updated = queryset.filter(status='planned').update(
            status='in_progress',
            started_at=timezone.now()
        )
        messages.success(request, f'Started {updated} stock takes.')
    
    @admin.action(description='Complete selected stock takes')
    def complete_stock_take(self, request, queryset):
        """Mark stock takes as completed"""
        updated = queryset.filter(status='in_progress').update(
            status='completed',
            completed_at=timezone.now()
        )
        messages.success(request, f'Completed {updated} stock takes.')


# =====================================
# DASHBOARD AND REPORTING
# =====================================

class InventoryAdminDashboard:
    """
    Custom admin dashboard views for inventory management.
    
    This provides executive-level visibility into your inventory
    operations with key metrics, alerts, and actionable insights.
    """
    
    @staticmethod
    def get_dashboard_context():
        """Get dashboard context data"""
        from django.db.models import Sum, Count, F
        
        # Key metrics
        total_products = Product.objects.filter(is_active=True).count()
        total_stock_value = Product.objects.filter(is_active=True).aggregate(
            total=Sum(F('current_stock') * F('cost_price'))
        )['total'] or Decimal('0.00')
        
        low_stock_count = Product.objects.filter(
            is_active=True,
            current_stock__lte=F('reorder_level')
        ).count()
        
        active_alerts = ReorderAlert.objects.filter(
            status__in=['active', 'acknowledged']
        ).count()
        
        pending_pos = PurchaseOrder.objects.filter(
            status__in=['draft', 'sent', 'acknowledged']
        ).count()
        
        return {
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'low_stock_count': low_stock_count,
            'active_alerts': active_alerts,
            'pending_pos': pending_pos,
        }


# =====================================
# ADMIN SITE CUSTOMIZATION
# =====================================

# Custom admin site title and headers
admin.site.site_header = "BlitzTech Electronics - Inventory Management"
admin.site.site_title = "Inventory Admin"
admin.site.index_title = "Inventory Management System"

# Register any additional admin customizations
admin.site.register(StockLevel)  # Simple registration for StockLevel if needed
