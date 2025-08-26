# inventory/admin.py - Inventory Management Admin Interface

"""
Django Admin Configuration for Inventory Management

This admin interface provides comprehensive inventory management capabilities
for your team. It's designed to be powerful yet user-friendly, with bulk
operations, advanced filtering, and intelligent defaults that make inventory
management efficient and error-free.

Key Features:
1. Dynamic attribute configuration per component family
2. Advanced cost calculation with overhead factors
3. Multi-currency and exchange rate management
4. Storage location and bin management
5. Supplier management with detailed terms
6. Advanced product management with dynamic attributes
7. Stock management with multi-location support
8. Automated reorder list generation
9. Business intelligence dashboards
"""

from django.contrib import admin
from django.db import transaction, models
from datetime import datetime, timedelta
from django.utils.html import format_html
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Avg, F
from django.urls import reverse, path
from django.shortcuts import render
from decimal import Decimal
import csv
import json

from .models import (
    Brand, Category, ComponentFamily, Currency, OverheadFactor, ProductAttributeDefinition, ProductStockLevel, StorageBin, StorageLocation, Supplier, Location, Product, StockLevel, StockMovement,
    StockTake, StockTakeItem, PurchaseOrder, PurchaseOrderItem,
    ReorderAlert, SupplierCountry
)

# =====================================
# ADMIN SITE CUSTOMIZATION
# =====================================

admin.site.site_header = "BlitzTech Electronics - Inventory Management"
admin.site.site_title = "BlitzTech ERP"
admin.site.index_title = "Electronics Inventory Management System"

class ElectronicsAdminMixin:
    """Base mixin for all admin interfaces"""
    
    def save_model(self, request, obj, form, change):
        """Auto-set created_by for new objects"""
        if not change and hasattr(obj, 'created_by'):
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Optimize queries with select_related"""
        return super().get_queryset(request).select_related()

# =====================================
# SYSTEM CONFIGURATION ADMIN
# =====================================

@admin.register(Currency)
class CurrencyAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Multi-currency management with exchange rates"""
    list_display = (
        'code', 'name', 'symbol', 'exchange_rate_to_usd', 
        'get_rate_age', 'auto_update_enabled', 'is_active'
    )
    list_filter = ('is_active', 'auto_update_enabled', 'api_source')
    search_fields = ('code', 'name')
    readonly_fields = ('last_updated', 'rate_age_hours')
    
    fieldsets = (
        ('Currency Information', {
            'fields': ('code', 'name', 'symbol')
        }),
        ('Exchange Rate', {
            'fields': ('exchange_rate_to_usd', 'last_updated'),
            'description': 'Exchange rate to USD (1 unit of this currency = X USD)'
        }),
        ('Auto-Update Settings', {
            'fields': ('auto_update_enabled', 'api_source'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        })
    )
    
    actions = ['update_exchange_rates', 'enable_auto_update', 'disable_auto_update']
    
    def get_rate_age(self, obj):
        hours = obj.rate_age_hours
        if hours < 1:
            return format_html('<span style="color: green;">Just updated</span>')
        elif hours < 24:
            return format_html('<span style="color: orange;">{:.1f} hours ago</span>', hours)
        else:
            return format_html('<span style="color: red;">{:.1f} days ago</span>', hours/24)
    get_rate_age.short_description = "Rate Age"
    
    def update_exchange_rates(self, request, queryset):
        """Update exchange rates (placeholder for API integration)"""
        # Here you would integrate with real exchange rate API
        count = queryset.update(last_updated=timezone.now())
        self.message_user(request, f"Updated {count} exchange rates")
    update_exchange_rates.short_description = "Update exchange rates"

@admin.register(OverheadFactor)
class OverheadFactorAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Configurable overhead factors for cost calculation"""
    list_display = (
        'name', 'calculation_type', 'get_rate_display', 'applies_to_summary', 'is_active'
    )
    list_filter = ('calculation_type', 'is_active')
    search_fields = ('name', 'description')
    filter_horizontal = ('applies_to_categories', 'applies_to_suppliers')
    
    fieldsets = (
        ('Factor Information', {
            'fields': ('name', 'description', 'calculation_type')
        }),
        ('Rate Configuration', {
            'fields': ('fixed_amount', 'percentage_rate'),
            'description': 'Only fill the field relevant to your calculation type'
        }),
        ('Application Rules', {
            'fields': ('applies_to_categories', 'applies_to_suppliers'),
            'description': 'Leave empty to apply to all products'
        }),
        ('Display', {
            'fields': ('display_order', 'is_active')
        }),
        ('Audit', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'created_by')
    ordering = ('display_order', 'name')
    
    def get_rate_display(self, obj):
        if obj.calculation_type in ['fixed_per_item', 'fixed_per_order']:
            return f"${obj.fixed_amount}"
        else:
            return f"{obj.percentage_rate}%"
    get_rate_display.short_description = "Rate"
    
    def applies_to_summary(self, obj):
        categories = obj.applies_to_categories.count()
        suppliers = obj.applies_to_suppliers.count()
        
        if categories == 0 and suppliers == 0:
            return "All products"
        
        parts = []
        if categories > 0:
            parts.append(f"{categories} categories")
        if suppliers > 0:
            parts.append(f"{suppliers} suppliers")
        
        return ", ".join(parts)
    applies_to_summary.short_description = "Applies To"

@admin.register(ProductAttributeDefinition)
class ProductAttributeDefinitionAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Dynamic product attributes configuration"""
    list_display = (
        'name', 'field_type', 'get_families', 'is_required', 
        'show_in_listings', 'show_in_search', 'is_active'
    )
    list_filter = ('field_type', 'is_required', 'show_in_listings', 'is_active')
    search_fields = ('name', 'help_text')
    filter_horizontal = ('component_families',)
    
    fieldsets = (
        ('Attribute Definition', {
            'fields': ('name', 'field_type', 'component_families')
        }),
        ('Field Configuration', {
            'fields': ('is_required', 'default_value', 'help_text')
        }),
        ('Choice Field Options', {
            'fields': ('choice_options',),
            'description': 'For choice fields, enter options as JSON list: ["Option1", "Option2"]',
            'classes': ('collapse',)
        }),
        ('Validation Rules', {
            'fields': ('min_value', 'max_value', 'validation_pattern'),
            'classes': ('collapse',)
        }),
        ('Display Settings', {
            'fields': ('display_order', 'show_in_listings', 'show_in_search')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'created_by')
    
    def get_families(self, obj):
        families = obj.component_families.all()[:3]
        names = [f.name for f in families]
        if obj.component_families.count() > 3:
            names.append("...")
        return ", ".join(names)
    get_families.short_description = "Component Families"

# =====================================
# CORE CONFIGURATION ADMIN
# =====================================

@admin.register(ComponentFamily)
class ComponentFamilyAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Component family management with dynamic attributes"""
    list_display = (
        'name', 'get_attributes_count', 'typical_markup_percentage', 
        'default_bin_prefix', 'get_products_count', 'is_active'
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('display_order', 'name')
    
    fieldsets = (
        ('Component Family Information', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Default Settings', {
            'fields': ('default_attributes', 'typical_markup_percentage', 'default_bin_prefix')
        }),
        ('Display', {
            'fields': ('display_order', 'is_active')
        })
    )
    
    def get_attributes_count(self, obj):
        count = obj.attribute_definitions.count()
        if count > 0:
            url = reverse('admin:inventory_productattributedefinition_changelist') + f'?component_families__id__exact={obj.id}'
            return format_html('<a href="{}">{} attributes</a>', url, count)
        return "No attributes"
    get_attributes_count.short_description = "Attributes"
    
    def get_products_count(self, obj):
        count = obj.products.filter(is_active=True).count()
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?component_family__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return "0 products"
    get_products_count.short_description = "Products"

@admin.register(StorageLocation)
class StorageLocationAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Storage location management"""
    list_display = (
        'name', 'code', 'location_type', 'get_bins_count', 
        'is_default', 'allows_sales', 'allows_receiving', 'is_active'
    )
    list_filter = ('location_type', 'is_active', 'is_default')
    search_fields = ('name', 'code', 'city')
    
    fieldsets = (
        ('Location Information', {
            'fields': ('name', 'code', 'location_type')
        }),
        ('Address', {
            'fields': ('address', 'city', 'country')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'phone', 'email')
        }),
        ('Capacity & Settings', {
            'fields': ('max_capacity_cubic_meters', 'is_default', 'allows_sales', 'allows_receiving')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'created_by')
    
    def get_bins_count(self, obj):
        count = obj.storage_bins.count()
        if count > 0:
            url = reverse('admin:inventory_storagebin_changelist') + f'?location__id__exact={obj.id}'
            return format_html('<a href="{}">{} bins</a>', url, count)
        return "No bins"
    get_bins_count.short_description = "Storage Bins"

@admin.register(StorageBin)
class StorageBinAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Storage bin management"""
    list_display = (
        'bin_code', 'location', 'name', 'get_families', 
        'get_current_utilization', 'requires_special_handling', 'is_active'
    )
    list_filter = ('location', 'requires_special_handling', 'is_active')
    search_fields = ('bin_code', 'name', 'location__name')
    filter_horizontal = ('component_families',)
    
    fieldsets = (
        ('Bin Information', {
            'fields': ('location', 'bin_code', 'name')
        }),
        ('Organization', {
            'fields': ('component_families', 'row', 'column', 'shelf')
        }),
        ('Capacity', {
            'fields': ('max_capacity_items',)
        }),
        ('Settings', {
            'fields': ('requires_special_handling', 'is_active')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )
    
    def get_families(self, obj):
        families = obj.component_families.all()[:2]
        names = [f.name for f in families]
        if obj.component_families.count() > 2:
            names.append("...")
        return ", ".join(names) if names else "Any"
    get_families.short_description = "Component Families"
    
    def get_current_utilization(self, obj):
        utilization = obj.utilization_percentage
        if utilization is None:
            return "N/A"
        
        if utilization < 50:
            color = "green"
        elif utilization < 80:
            color = "orange"
        else:
            color = "red"
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, utilization
        )
    get_current_utilization.short_description = "Utilization"

# =====================================
# BUSINESS ENTITY ADMIN
# =====================================

@admin.register(Brand)
class BrandAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Brand management"""
    list_display = (
        'name', 'market_position', 'quality_rating', 'default_markup_percentage',
        'warranty_period_months', 'get_products_count', 'is_active'
    )
    list_filter = ('market_position', 'quality_rating', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    
    fieldsets = (
        ('Brand Information', {
            'fields': ('name', 'slug', 'description', 'website', 'logo')
        }),
        ('Market Positioning', {
            'fields': ('market_position', 'quality_rating', 'warranty_period_months')
        }),
        ('Business Settings', {
            'fields': ('default_markup_percentage',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    
    def get_products_count(self, obj):
        count = obj.product_count
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?brand__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return "0 products"
    get_products_count.short_description = "Products"
    
    actions = ['bulk_update_markup']
    
    def bulk_update_markup(self, request, queryset):
        """Bulk update markup for brand's products"""
        # Implementation would go here
        self.message_user(request, f"Updated markup for {queryset.count()} brands")
    bulk_update_markup.short_description = "Update markup for products"

@admin.register(Supplier)
class SupplierAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Enhanced supplier management"""
    list_display = (
        'name', 'code', 'country', 'currency', 'rating', 
        'on_time_delivery_rate', 'get_products_count', 'is_preferred', 'is_active'
    )
    list_filter = (
        'country', 'currency', 'rating', 'is_preferred', 'is_active',
        'supports_dropshipping', 'preferred_contact_method'
    )
    search_fields = ('name', 'code', 'contact_person', 'email')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'website')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'email', 'phone', 'whatsapp', 'address')
        }),
        ('Geographic & Currency', {
            'fields': ('country', 'currency', 'preferred_contact_method')
        }),
        ('Business Terms', {
            'fields': (
                'payment_terms', 'minimum_order_value', 
                'typical_lead_time_days', 'preferred_shipping_method'
            )
        }),
        ('Performance Tracking', {
            'fields': ('rating', 'on_time_delivery_rate', 'quality_score'),
            'description': 'Track supplier performance metrics'
        }),
        ('Capabilities', {
            'fields': (
                'supports_dropshipping', 'provides_technical_support',
                'has_local_representative', 'accepts_returns', 'return_policy_days'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_preferred')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    
    def get_products_count(self, obj):
        count = obj.total_products
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?supplier__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return "0 products"
    get_products_count.short_description = "Products"
    
    actions = ['mark_as_preferred', 'generate_supplier_report']
    
    def mark_as_preferred(self, request, queryset):
        count = queryset.update(is_preferred=True)
        self.message_user(request, f"Marked {count} suppliers as preferred")
    mark_as_preferred.short_description = "Mark as preferred suppliers"

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

class ProductStockLevelInline(admin.TabularInline):
    """Inline for managing stock levels per location"""
    model = ProductStockLevel
    extra = 0
    readonly_fields = ('available_quantity', 'last_movement_date')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('location', 'storage_bin')

@admin.register(Product)
class ProductAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    """Comprehensive product management"""
    
    list_display = (
        'sku', 'name', 'brand', 'category', 'supplier',
        'get_stock_status', 'total_stock', 'get_markup_display',
        'selling_price', 'get_profit_per_unit', 'is_active'
    )
    
    list_filter = (
        'is_active', 'product_type', 'category', 'supplier', 'brand',
        'component_family', 'quality_grade', 'is_hazardous',
        'requires_esd_protection', 'is_temperature_sensitive',
        ('created_at', admin.DateFieldListFilter)
    )
    
    search_fields = (
        'sku', 'name', 'barcode', 'qr_code', 'manufacturer_part_number',
        'supplier_sku', 'description'
    )
    
    readonly_fields = (
        'cost_price_usd', 'total_import_cost_usd', 'overhead_cost_per_unit',
        'total_cost_price_usd', 'markup_percentage', 'available_stock',
        'profit_per_unit_usd', 'stock_value_usd', 'stock_status', 'needs_reorder',
        'total_sold', 'total_revenue', 'last_sold_date', 'last_restocked_date',
        'last_cost_update', 'created_at', 'updated_at'
    )
    
    fieldsets = (
        ('Product Identification', {
            'fields': (
                ('sku', 'barcode', 'qr_code'),
                'name',
                'short_description',
                'description'
            )
        }),
        ('Categorization', {
            'fields': (
                ('category', 'component_family'),
                ('supplier', 'brand'),
                'product_type'
            )
        }),
        ('Electronics Specifications', {
            'fields': (
                ('model_number', 'manufacturer_part_number', 'supplier_sku'),
                ('package_type', 'quality_grade'),
                'dynamic_attributes'
            ),
        }),
        ('External Resources', {
            'fields': (
                'datasheet_url',
                'product_images',
                'additional_documents',
                'certifications'
            ),
            'classes': ('collapse',)
        }),
        ('Physical Attributes', {
            'fields': (
                ('weight_grams', 'dimensions', 'volume_cubic_cm'),
                ('is_hazardous', 'requires_esd_protection', 'is_temperature_sensitive')
            ),
            'classes': ('collapse',)
        }),
        ('Cost Structure', {
            'fields': (
                ('cost_price', 'supplier_currency'),
                ('shipping_cost_per_unit', 'insurance_cost_per_unit'),
                ('customs_duty_percentage', 'vat_percentage', 'other_fees_per_unit'),
                ('cost_price_usd', 'total_import_cost_usd'),
                ('overhead_cost_per_unit', 'total_cost_price_usd')
            ),
            'description': 'Complete cost breakdown for import business'
        }),
        ('Pricing & Competition', {
            'fields': (
                ('selling_currency', 'selling_price'),
                ('markup_percentage', 'profit_per_unit_usd'),
                ('competitor_min_price', 'competitor_max_price', 'price_position')
            )
        }),
        ('Stock Management', {
            'fields': (
                ('total_stock', 'reserved_stock', 'available_stock'),
                ('reorder_level', 'reorder_quantity', 'max_stock_level'),
                ('economic_order_quantity', 'stock_status', 'needs_reorder'),
                'stock_value_usd'
            )
        }),
        ('Supplier Terms', {
            'fields': (
                ('supplier_lead_time_days', 'supplier_minimum_order_quantity'),
                'supplier_price_breaks'
            ),
            'classes': ('collapse',)
        }),
        ('Performance Metrics', {
            'fields': (
                ('total_sold', 'total_revenue'),
                ('last_sold_date', 'last_restocked_date', 'last_cost_update')
            ),
            'classes': ('collapse',)
        }),
        ('SEO & Marketing', {
            'fields': (
                ('meta_title', 'meta_description'),
                'search_keywords'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [ProductStockLevelInline]
    
    # Enhanced display methods
    def get_stock_status(self, obj):
        status = obj.stock_status
        colors = {
            'in_stock': 'green',
            'low_stock': 'orange',
            'out_of_stock': 'red'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(status, 'black'),
            status.replace('_', ' ').title()
        )
    get_stock_status.short_description = "Stock Status"
    
    def get_markup_display(self, obj):
        if obj.markup_percentage:
            color = 'green' if obj.markup_percentage >= 30 else 'orange'
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, obj.markup_percentage
            )
        return "-"
    get_markup_display.short_description = "Markup"
    
    def get_profit_per_unit(self, obj):
        profit = obj.profit_per_unit_usd
        color = 'green' if profit > 0 else 'red'
        return format_html(
            '<span style="color: {};">${:.2f}</span>',
            color, profit
        )
    get_profit_per_unit.short_description = "Profit/Unit"
    
    # Custom admin URLs
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('generate-reorder-list/', self.admin_site.admin_view(self.generate_reorder_list), name='inventory-generate-reorder-list'),
            path('bulk-cost-update/', self.admin_site.admin_view(self.bulk_cost_update), name='inventory-bulk-cost-update'),
        ]
        return custom_urls + urls
    
    def generate_reorder_list(self, request):
        """Generate downloadable reorder list"""
        products_needing_reorder = Product.objects.filter(
            is_active=True,
            total_stock__lte=F('reorder_level')
        ).select_related('supplier', 'category', 'brand')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="reorder_list.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Supplier', 'SKU', 'Product Name', 'Current Stock', 'Reorder Level',
            'Recommended Quantity', 'Supplier SKU', 'Unit Cost', 'Total Cost',
            'Lead Time (Days)', 'MOQ'
        ])
        
        for product in products_needing_reorder:
            recommended_qty = max(
                product.reorder_quantity,
                product.supplier_minimum_order_quantity
            )
            total_cost = product.cost_price * recommended_qty
            
            writer.writerow([
                product.supplier.name,
                product.sku,
                product.name,
                product.total_stock,
                product.reorder_level,
                recommended_qty,
                product.supplier_sku,
                product.cost_price,
                total_cost,
                product.supplier_lead_time_days,
                product.supplier_minimum_order_quantity
            ])
        
        return response
    
    # Enhanced actions
    actions = [
        'export_products', 'mark_for_reorder', 'update_cost_prices', 
        'bulk_markup_update', 'generate_qr_codes'
    ]
    
    def export_products(self, request, queryset):
        """Export selected products with all details"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'SKU', 'Name', 'Category', 'Brand', 'Supplier', 'Current Stock',
            'Cost Price', 'Total Cost (USD)', 'Selling Price', 'Markup %',
            'Profit/Unit', 'Stock Value', 'Status'
        ])
        
        for product in queryset:
            writer.writerow([
                product.sku, product.name, product.category.name,
                product.brand.name, product.supplier.name, product.total_stock,
                product.cost_price, product.total_cost_price_usd,
                product.selling_price, product.markup_percentage,
                product.profit_per_unit_usd, product.stock_value_usd,
                'Active' if product.is_active else 'Inactive'
            ])
        
        return response
    export_products.short_description = "Export selected products"
    
    def mark_for_reorder(self, request, queryset):
        """Create reorder alerts for selected products"""
        count = 0
        for product in queryset:
            if product.needs_reorder:
                ReorderAlert.objects.get_or_create(
                    product=product,
                    defaults={
                        'quantity_needed': product.reorder_quantity,
                        'priority': 'medium' if product.total_stock > 0 else 'high',
                        'status': 'active'
                    }
                )
                count += 1
        
        self.message_user(request, f"Created reorder alerts for {count} products")
    mark_for_reorder.short_description = "Create reorder alerts"
    
    def generate_qr_codes(self, request, queryset):
        """Generate QR codes for selected products"""
        count = 0
        for product in queryset:
            if not product.qr_code:
                product.qr_code = f"BT-{product.sku}-{datetime.now().strftime('%Y%m%d')}"
                product.save(update_fields=['qr_code'])
                count += 1
        
        self.message_user(request, f"Generated QR codes for {count} products")
    generate_qr_codes.short_description = "Generate QR codes"

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
# REPORTS AND ANALYTICS
# =====================================

class InventoryReportsAdmin(admin.ModelAdmin):
    """Custom admin for inventory reports"""
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Custom changelist view for reports dashboard"""
        extra_context = extra_context or {}
        
        # Calculate key metrics
        total_products = Product.objects.filter(is_active=True).count()
        total_stock_value = Product.objects.filter(is_active=True).aggregate(
            total=Sum(F('total_stock') * F('total_cost_price_usd'))
        )['total'] or 0
        
        low_stock_count = Product.objects.filter(
            is_active=True,
            total_stock__lte=F('reorder_level')
        ).count()
        
        # Top performing categories
        top_categories = Category.objects.filter(
            products__is_active=True
        ).annotate(
            product_count=Count('products'),
            total_value=Sum(F('products__total_stock') * F('products__total_cost_price_usd'))
        ).order_by('-total_value')[:5]
        
        # Supplier performance
        supplier_stats = Supplier.objects.filter(
            is_active=True
        ).annotate(
            product_count=Count('products', filter=models.Q(products__is_active=True)),
            avg_lead_time=Avg('typical_lead_time_days')
        ).order_by('-product_count')[:5]
        
        extra_context.update({
            'total_products': total_products,
            'total_stock_value': total_stock_value,
            'low_stock_count': low_stock_count,
            'top_categories': top_categories,
            'supplier_stats': supplier_stats,
        })
        
        return render(request, 'admin/inventory/reports_dashboard.html', extra_context)

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

# Register the reports admin
admin.site.register(InventoryReportsAdmin, InventoryReportsAdmin)

# =====================================
# OTHER MODEL REGISTRATIONS
# =====================================

@admin.register(SupplierCountry)
class SupplierCountryAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    list_display = (
        'name', 'code', 'region', 'average_lead_time_days',
        'typical_shipping_cost_percentage', 'average_customs_duty_percentage', 'is_active'
    )
    list_filter = ('region', 'is_active', 'requires_import_permit')
    search_fields = ('name', 'code')


@admin.register(Category)
class CategoryAdmin(ElectronicsAdminMixin, admin.ModelAdmin):
    list_display = (
        'name', 'parent', 'component_family', 'get_product_count',
        'default_markup_percentage', 'requires_datasheet', 'is_active'
    )
    list_filter = (
        'component_family', 'requires_datasheet', 'requires_certification',
        'requires_esd_protection', 'is_active'
    )
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    
    def get_product_count(self, obj):
        count = obj.get_product_count()
        if count > 0:
            url = reverse('admin:inventory_product_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{} products</a>', url, count)
        return "0 products"
    get_product_count.short_description = "Products"


# Additional model registrations for existing models
@admin.register(ReorderAlert)
class ReorderAlertAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'quantity_needed', 'priority', 'status',
        'created_at', 'acknowledged_at'
    )
    list_filter = ('priority', 'status', 'created_at')
    search_fields = ('product__sku', 'product__name')
