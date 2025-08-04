# inventory/forms.py - Comprehensive Inventory Management Forms

"""
Django Forms for Inventory Management

This module provides user-friendly forms for all inventory operations with
intelligent validation, business logic integration, and enhanced user experience.

Key Features:
- Smart field validation with business rules
- Dynamic form fields based on user permissions
- Integration with existing core system
- AJAX-ready forms for seamless user experience
- Bulk operation forms for efficiency
- Mobile-friendly responsive design
"""

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal
from django.utils import timezone
import re

from .models import (
    Category, Supplier, Location, Product, StockLevel, StockMovement,
    StockTake, StockTakeItem, PurchaseOrder, PurchaseOrderItem, ReorderAlert
)


# =====================================
# BASE FORM CLASSES AND MIXINS
# =====================================

class InventoryBaseForm(forms.ModelForm):
    """
    Base form class for inventory management with common functionality.
    
    This base class provides consistent behavior across all inventory forms
    including Bootstrap styling, user context awareness, and integration
    with your existing permission system.
    """
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Apply Bootstrap styling to all form fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 3})
            else:
                field.widget.attrs.update({'class': 'form-control'})
        
        # Add helpful attributes for better UX
        self._add_field_helpers()
    
    def _add_field_helpers(self):
        """Add helpful attributes and validation to form fields"""
        for field_name, field in self.fields.items():
            # Add placeholder text based on field name
            if not field.widget.attrs.get('placeholder'):
                placeholder = self._generate_placeholder(field_name, field)
                if placeholder:
                    field.widget.attrs['placeholder'] = placeholder
            
            # Add required indicators
            if field.required:
                field.widget.attrs['required'] = True
    
    def _generate_placeholder(self, field_name, field):
        """Generate helpful placeholder text for fields"""
        placeholders = {
            'name': 'Enter a descriptive name',
            'sku': 'Product SKU (e.g., BT-2024-001)',
            'barcode': 'Barcode or QR code',
            'cost_price': '0.00',
            'selling_price': '0.00',
            'current_stock': '0',
            'reorder_level': '10',
            'email': 'supplier@example.com',
            'phone': '+263 XX XXX XXXX',
            'website': 'https://supplier-website.com',
            'supplier_code': 'SUP-001',
            'location_code': 'LOC-001',
            'po_number': 'PO-' + str(timezone.now().year) + '-001',
        }
        
        return placeholders.get(field_name, '')
    
    def clean(self):
        """Enhanced form validation with business logic"""
        cleaned_data = super().clean()
        
        # Perform user-specific validation
        if self.user:
            self._validate_user_permissions(cleaned_data)
        
        return cleaned_data
    
    def _validate_user_permissions(self, cleaned_data):
        """Validate data based on user permissions"""
        # This can be overridden in specific forms for custom validation
        pass

class AjaxResponseMixin:
    """
    Mixin for forms that need to handle AJAX responses.
    
    Provides consistent AJAX response handling across inventory forms.
    """
    
    def get_ajax_response_data(self):
        """Get data for AJAX response"""
        return {
            'success': True,
            'message': 'Operation completed successfully',
            'object_id': self.instance.pk if hasattr(self, 'instance') else None
        }
    
    def get_ajax_error_response(self, form_errors):
        """Get error response for AJAX"""
        return {
            'success': False,
            'errors': form_errors,
            'message': 'Please correct the errors below'
        }


# =====================================
# CATEGORY MANAGEMENT FORMS
# =====================================

class CategoryForm(InventoryBaseForm):
    """
    Category creation and editing form with hierarchical support.
    
    Handles product category management with parent-child relationships
    and intelligent validation to prevent circular references.
    """
    
    class Meta:
        model = Category
        fields = [
            'name', 'slug', 'parent', 'description',
            'default_markup_percentage', 'default_reorder_level',
            'display_order', 'is_active'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'default_markup_percentage': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0', 'max': '1000'
            }),
            'default_reorder_level': forms.NumberInput(attrs={
                'min': '0', 'max': '10000'
            }),
            'display_order': forms.NumberInput(attrs={
                'min': '0', 'max': '999'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Prevent selecting self as parent for existing categories
        if self.instance and self.instance.pk:
            self.fields['parent'].queryset = Category.objects.exclude(
                Q(pk=self.instance.pk) | Q(parent=self.instance)
            )
        
        # Add helpful help texts
        self.fields['slug'].help_text = 'URL-friendly version of the name (auto-generated if left blank)'
        self.fields['default_markup_percentage'].help_text = 'Default profit margin for products in this category'
        self.fields['default_reorder_level'].help_text = 'Default minimum stock level for products'
    
    def clean_slug(self):
        """Auto-generate slug if not provided"""
        slug = self.cleaned_data.get('slug')
        name = self.cleaned_data.get('name')
        
        if not slug and name:
            from django.utils.text import slugify
            slug = slugify(name)
        
        # Ensure slug is unique
        if slug:
            existing = Category.objects.filter(slug=slug)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A category with this slug already exists.')
        
        return slug
    
    def clean_parent(self):
        """Prevent circular references in category hierarchy"""
        parent = self.cleaned_data.get('parent')
        
        if parent and self.instance.pk:
            # Check if the selected parent would create a circular reference
            if self._would_create_circular_reference(parent):
                raise ValidationError(
                    'Cannot set this parent as it would create a circular reference.'
                )
        
        return parent
    
    def _would_create_circular_reference(self, potential_parent):
        """Check if setting this parent would create a circular reference"""
        current = potential_parent
        while current:
            if current.pk == self.instance.pk:
                return True
            current = current.parent
        return False

class CategoryBulkUpdateForm(forms.Form):
    """
    Bulk update form for category management.
    
    Allows updating multiple categories at once for efficiency.
    """
    
    ACTION_CHOICES = [
        ('update_markup', 'Update Default Markup'),
        ('update_reorder_level', 'Update Default Reorder Level'),
        ('activate', 'Activate Categories'),
        ('deactivate', 'Deactivate Categories'),
    ]
    
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    action = forms.ChoiceField(choices=ACTION_CHOICES, required=True)
    new_markup_percentage = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    new_reorder_level = forms.IntegerField(
        min_value=0, required=False,
        widget=forms.NumberInput(attrs={'min': '0'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'update_markup' and not cleaned_data.get('new_markup_percentage'):
            raise ValidationError('Markup percentage is required for markup updates.')
        
        if action == 'update_reorder_level' and not cleaned_data.get('new_reorder_level'):
            raise ValidationError('Reorder level is required for reorder level updates.')
        
        return cleaned_data


# =====================================
# SUPPLIER MANAGEMENT FORMS
# =====================================

class SupplierForm(InventoryBaseForm):
    """
    Comprehensive supplier management form.
    
    Handles all aspects of supplier relationship management with
    validation for business terms and contact information.
    """
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'supplier_code', 'supplier_type', 'contact_person',
            'email', 'phone', 'website',
            'address_line_1', 'address_line_2', 'city', 'state_province',
            'postal_code', 'country',
            'payment_terms', 'currency', 'minimum_order_amount',
            'average_lead_time_days', 'reliability_rating',
            'tax_number', 'requires_purchase_order',
            'is_active', 'is_preferred', 'notes'
        ]
        widgets = {
            'reliability_rating': forms.NumberInput(attrs={
                'step': '0.1', 'min': '1', 'max': '10'
            }),
            'minimum_order_amount': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0'
            }),
            'average_lead_time_days': forms.NumberInput(attrs={
                'min': '1', 'max': '365'
            }),
            'notes': forms.Textarea(attrs={'rows': 4})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make certain fields required for better data quality
        self.fields['contact_person'].required = True
        self.fields['phone'].required = True
        self.fields['address_line_1'].required = True
        self.fields['city'].required = True
        self.fields['country'].required = True
        
        # Add help texts
        self.fields['supplier_code'].help_text = 'Unique identifier for this supplier'
        self.fields['reliability_rating'].help_text = 'Rate from 1-10 based on delivery performance'
        self.fields['average_lead_time_days'].help_text = 'Average delivery time in days'
    
    def clean_supplier_code(self):
        """Ensure supplier code is unique"""
        code = self.cleaned_data.get('supplier_code')
        
        if code:
            existing = Supplier.objects.filter(supplier_code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A supplier with this code already exists.')
        
        return code
    
    def clean_email(self):
        """Validate email format and uniqueness"""
        email = self.cleaned_data.get('email')
        
        if email:
            # Check for uniqueness
            existing = Supplier.objects.filter(email=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A supplier with this email already exists.')
        
        return email
    
    def clean_website(self):
        """Ensure website URL is properly formatted"""
        website = self.cleaned_data.get('website')
        
        if website and not website.startswith(('http://', 'https://')):
            website = 'https://' + website
        
        return website

class SupplierSearchForm(forms.Form):
    """
    Advanced supplier search and filtering form.
    
    Provides multiple search criteria for finding suppliers efficiently.
    """
    
    search = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, code, or contact person...'
        })
    )
    supplier_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(Supplier.SUPPLIER_TYPES),
        required=False
    )
    country = forms.CharField(max_length=100, required=False)
    currency = forms.ChoiceField(
        choices=[('', 'All Currencies')] + list(Supplier.CURRENCY_CHOICES),
        required=False
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False
    )
    is_preferred = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Preferred'), ('false', 'Standard')],
        required=False
    )
    min_rating = forms.DecimalField(
        max_digits=3, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'step': '0.1', 'min': '1', 'max': '10'})
    )


# =====================================
# LOCATION MANAGEMENT FORMS
# =====================================

class LocationForm(InventoryBaseForm):
    """
    Location management form for multi-location inventory.
    
    Handles storage location configuration with capacity management
    and operational settings.
    """
    
    class Meta:
        model = Location
        fields = [
            'name', 'location_code', 'location_type', 'address',
            'contact_person', 'phone', 'max_capacity',
            'is_active', 'is_sellable', 'is_default'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'max_capacity': forms.NumberInput(attrs={'min': '1'})
        }
    
    def clean_location_code(self):
        """Ensure location code is unique"""
        code = self.cleaned_data.get('location_code')
        
        if code:
            existing = Location.objects.filter(location_code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A location with this code already exists.')
        
        return code
    
    def clean(self):
        cleaned_data = super().clean()
        
        # If setting as default, ensure only one default location exists
        if cleaned_data.get('is_default'):
            existing_default = Location.objects.filter(is_default=True)
            if self.instance.pk:
                existing_default = existing_default.exclude(pk=self.instance.pk)
            
            if existing_default.exists():
                self.add_error(
                    'is_default',
                    'Another location is already set as default. Only one default location is allowed.'
                )
        
        return cleaned_data


# =====================================
# PRODUCT MANAGEMENT FORMS
# =====================================

class ProductForm(InventoryBaseForm):
    """
    Comprehensive product management form.
    
    This is the core form for product creation and editing with
    intelligent validation, cost calculation, and integration
    with categories and suppliers.
    """
    
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'barcode', 'description', 'short_description',
            'category', 'supplier', 'product_type', 'brand', 'model_number',
            'manufacturer_part_number', 'weight', 'dimensions',
            'cost_price', 'selling_price', 'currency',
            'reorder_level', 'reorder_quantity', 'max_stock_level',
            'supplier_sku', 'supplier_lead_time_days', 'minimum_order_quantity',
            'is_active', 'is_serialized', 'is_perishable', 'requires_quality_check',
            'meta_title', 'meta_description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.Textarea(attrs={'rows': 2}),
            'cost_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'weight': forms.NumberInput(attrs={'step': '0.001', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'min': '0'}),
            'reorder_quantity': forms.NumberInput(attrs={'min': '1'}),
            'max_stock_level': forms.NumberInput(attrs={'min': '1'}),
            'supplier_lead_time_days': forms.NumberInput(attrs={'min': '1', 'max': '365'}),
            'minimum_order_quantity': forms.NumberInput(attrs={'min': '1'}),
            'meta_description': forms.Textarea(attrs={'rows': 2})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter suppliers to only active ones
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        
        # Add calculated field display
        if self.instance and self.instance.pk:
            self.fields['profit_margin'] = forms.CharField(
                initial=f"{self.instance.profit_margin_percentage:.2f}%",
                widget=forms.TextInput(attrs={'readonly': True}),
                required=False,
                help_text='Calculated automatically based on cost and selling price'
            )
        
        # Add helpful help texts
        self.fields['sku'].help_text = 'Unique product identifier (auto-generated if left blank)'
        self.fields['barcode'].help_text = 'Barcode or QR code for scanning'
        self.fields['weight'].help_text = 'Weight in kilograms'
        self.fields['dimensions'].help_text = 'Length x Width x Height in centimeters'
    
    def clean_sku(self):
        """Auto-generate SKU if not provided and ensure uniqueness"""
        sku = self.cleaned_data.get('sku')
        
        if not sku:
            # Auto-generate SKU based on category and year
            category = self.cleaned_data.get('category')
            if category:
                from django.utils import timezone
                year = timezone.now().year
                category_prefix = category.name[:3].upper()
                
                # Find the next available number
                existing_skus = Product.objects.filter(
                    sku__startswith=f"{category_prefix}-{year}-"
                ).values_list('sku', flat=True)
                
                next_number = 1
                while f"{category_prefix}-{year}-{next_number:03d}" in existing_skus:
                    next_number += 1
                
                sku = f"{category_prefix}-{year}-{next_number:03d}"
        
        # Check uniqueness
        if sku:
            existing = Product.objects.filter(sku=sku)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A product with this SKU already exists.')
        
        return sku
    
    def clean_barcode(self):
        """Ensure barcode uniqueness if provided"""
        barcode = self.cleaned_data.get('barcode')
        
        if barcode:
            existing = Product.objects.filter(barcode=barcode)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A product with this barcode already exists.')
        
        return barcode
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate pricing
        cost_price = cleaned_data.get('cost_price')
        selling_price = cleaned_data.get('selling_price')
        
        if cost_price and selling_price:
            if selling_price < cost_price:
                self.add_error(
                    'selling_price',
                    'Selling price cannot be less than cost price.'
                )
            
            # Warn about very low margins
            margin = ((selling_price - cost_price) / cost_price) * 100 if cost_price > 0 else 0
            if margin < 5:
                self.add_error(
                    'selling_price',
                    'Warning: Profit margin is very low (less than 5%).'
                )
        
        # Validate stock levels
        reorder_level = cleaned_data.get('reorder_level')
        max_stock_level = cleaned_data.get('max_stock_level')
        
        if reorder_level and max_stock_level:
            if reorder_level >= max_stock_level:
                self.add_error(
                    'reorder_level',
                    'Reorder level must be less than maximum stock level.'
                )
        
        return cleaned_data

class ProductBulkUpdateForm(forms.Form):
    """
    Bulk update form for product management.
    
    Allows efficient bulk operations on multiple products.
    """
    
    ACTION_CHOICES = [
        ('update_prices', 'Update Prices'),
        ('apply_markup', 'Apply Markup Percentage'),
        ('update_supplier', 'Update Supplier'),
        ('update_category', 'Update Category'),
        ('activate', 'Activate Products'),
        ('deactivate', 'Deactivate Products'),
    ]
    
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    action = forms.ChoiceField(choices=ACTION_CHOICES, required=True)
    
    # Price update fields
    cost_price_adjustment = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text='Amount to add/subtract from cost price'
    )
    selling_price_adjustment = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text='Amount to add/subtract from selling price'
    )
    markup_percentage = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        help_text='Markup percentage to apply to cost price'
    )
    
    # Update fields
    new_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False
    )
    new_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False
    )


# =====================================
# STOCK MANAGEMENT FORMS
# =====================================

class StockAdjustmentForm(forms.Form):
    """
    Stock adjustment form for manual inventory changes.
    
    Handles positive and negative stock adjustments with
    proper validation and audit trail creation.
    """
    
    ADJUSTMENT_TYPES = [
        ('set', 'Set to specific amount'),
        ('add', 'Add to current stock'),
        ('subtract', 'Subtract from current stock'),
    ]
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPES,
        widget=forms.RadioSelect
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'min': '0'})
    )
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'placeholder': 'Reason for stock adjustment...'
        })
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        help_text='Leave blank for all locations'
    )
    notes = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default location if available
        default_location = Location.objects.filter(is_default=True).first()
        if default_location:
            self.fields['location'].initial = default_location
    
    def clean(self):
        cleaned_data = super().clean()
        
        product = cleaned_data.get('product')
        adjustment_type = cleaned_data.get('adjustment_type')
        quantity = cleaned_data.get('quantity')
        
        if product and adjustment_type == 'subtract' and quantity:
            if quantity > product.current_stock:
                raise ValidationError(
                    f'Cannot subtract {quantity} from current stock of {product.current_stock}'
                )
        
        return cleaned_data

class StockTransferForm(forms.Form):
    """
    Stock transfer form for moving inventory between locations.
    
    Enables efficient stock transfers with proper validation
    and automatic movement tracking.
    """
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True)
    )
    from_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        label='From Location'
    )
    to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        label='To Location'
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'min': '1'})
    )
    reference = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'placeholder': 'Transfer reference number...'
        })
    )
    notes = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False
    )
    
    def clean(self):
        cleaned_data = super().clean()
        
        from_location = cleaned_data.get('from_location')
        to_location = cleaned_data.get('to_location')
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        # Ensure different locations
        if from_location and to_location and from_location == to_location:
            raise ValidationError('From and To locations must be different.')
        
        # Check available stock at from location
        if from_location and product and quantity:
            try:
                stock_level = StockLevel.objects.get(
                    product=product, location=from_location
                )
                if quantity > stock_level.available_quantity:
                    raise ValidationError(
                        f'Only {stock_level.available_quantity} units available at {from_location.name}'
                    )
            except StockLevel.DoesNotExist:
                raise ValidationError(
                    f'No stock available for {product.name} at {from_location.name}'
                )
        
        return cleaned_data


# =====================================
# PURCHASE ORDER FORMS
# =====================================

class PurchaseOrderForm(InventoryBaseForm):
    """
    Purchase order creation and management form.
    
    Handles the complete purchase order workflow with
    supplier integration and delivery management.
    """
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'po_number', 'supplier', 'expected_delivery_date',
            'delivery_location', 'delivery_instructions',
            'payment_terms', 'notes'
        ]
        widgets = {
            'expected_delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'delivery_instructions': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to active suppliers
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        
        # Set default delivery location
        default_location = Location.objects.filter(is_default=True).first()
        if default_location:
            self.fields['delivery_location'].initial = default_location
        
        # Auto-generate PO number if creating new
        if not self.instance.pk:
            from django.utils import timezone
            today = timezone.now().date()
            
            # Find next PO number for today
            existing_pos = PurchaseOrder.objects.filter(
                po_number__startswith=f"PO-{today.strftime('%Y%m%d')}"
            ).count()
            
            next_number = existing_pos + 1
            self.fields['po_number'].initial = f"PO-{today.strftime('%Y%m%d')}-{next_number:03d}"
    
    def clean_po_number(self):
        """Ensure PO number uniqueness"""
        po_number = self.cleaned_data.get('po_number')
        
        if po_number:
            existing = PurchaseOrder.objects.filter(po_number=po_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A purchase order with this number already exists.')
        
        return po_number

class PurchaseOrderItemForm(forms.ModelForm):
    """
    Purchase order line item form.
    
    Handles individual items within purchase orders with
    quantity and pricing validation.
    """
    
    class Meta:
        model = PurchaseOrderItem
        fields = [
            'product', 'quantity_ordered', 'unit_price',
            'expected_delivery_date', 'notes'
        ]
        widgets = {
            'quantity_ordered': forms.NumberInput(attrs={'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'expected_delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter to active products
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        
        # Set initial unit price from product cost if available
        if 'product' in self.initial:
            try:
                product = Product.objects.get(pk=self.initial['product'])
                self.fields['unit_price'].initial = product.cost_price
            except Product.DoesNotExist:
                pass

# PurchaseOrderItemFormSet for managing multiple items
from django.forms import formset_factory
PurchaseOrderItemFormSet = formset_factory(
    PurchaseOrderItemForm,
    extra=1,
    can_delete=True
)


# =====================================
# STOCK TAKE FORMS
# =====================================

class StockTakeForm(InventoryBaseForm):
    """
    Stock take planning and management form.
    
    Handles physical inventory counting operations with
    scheduling and location management.
    """
    
    class Meta:
        model = StockTake
        fields = [
            'reference', 'description', 'location',
            'scheduled_date', 'notes'
        ]
        widgets = {
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.TextInput(attrs={
                'placeholder': 'e.g., Monthly stock count - Main warehouse'
            }),
            'notes': forms.Textarea(attrs={'rows': 3})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Auto-generate reference if creating new
        if not self.instance.pk:
            from django.utils import timezone
            today = timezone.now().date()
            
            existing_counts = StockTake.objects.filter(
                reference__startswith=f"ST-{today.strftime('%Y%m%d')}"
            ).count()
            
            next_number = existing_counts + 1
            self.fields['reference'].initial = f"ST-{today.strftime('%Y%m%d')}-{next_number:03d}"

class StockTakeItemForm(forms.ModelForm):
    """
    Individual stock take item counting form.
    
    Used for recording physical counts during stock takes.
    """
    
    class Meta:
        model = StockTakeItem
        fields = [
            'product', 'location', 'counted_quantity', 'notes'
        ]
        widgets = {
            'counted_quantity': forms.NumberInput(attrs={'min': '0'}),
            'notes': forms.Textarea(attrs={'rows': 2})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Show system quantity for reference
        if self.instance and self.instance.pk:
            self.fields['system_quantity'] = forms.IntegerField(
                initial=self.instance.system_quantity,
                widget=forms.NumberInput(attrs={'readonly': True}),
                required=False,
                label='System Quantity'
            )


# =====================================
# SEARCH AND FILTER FORMS
# =====================================

class ProductSearchForm(forms.Form):
    """
    Advanced product search form with multiple criteria.
    
    Provides comprehensive search and filtering capabilities
    for finding products efficiently.
    """
    
    search = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, SKU, or barcode...',
            'class': 'form-control'
        })
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False, empty_label='All Categories'
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False, empty_label='All Suppliers'
    )
    stock_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock')
        ],
        required=False
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False
    )
    min_price = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )
    max_price = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
    )

class InventoryReportForm(forms.Form):
    """
    Form for generating inventory reports with customizable parameters.
    
    Allows users to specify report criteria and output formats.
    """
    
    REPORT_TYPES = [
        ('stock_levels', 'Current Stock Levels'),
        ('low_stock', 'Low Stock Report'),
        ('stock_movements', 'Stock Movement History'),
        ('valuation', 'Inventory Valuation'),
        ('reorder_alerts', 'Reorder Recommendations'),
    ]
    
    OUTPUT_FORMATS = [
        ('html', 'View in Browser'),
        ('csv', 'Download CSV'),
        ('pdf', 'Download PDF'),
    ]
    
    report_type = forms.ChoiceField(choices=REPORT_TYPES, required=True)
    output_format = forms.ChoiceField(choices=OUTPUT_FORMATS, required=True)
    
    # Date range filters
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # Category and supplier filters
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    suppliers = forms.ModelMultipleChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    
    # Report options
    include_inactive = forms.BooleanField(
        required=False,
        label='Include inactive products'
    )
    group_by_category = forms.BooleanField(
        required=False,
        label='Group results by category'
    )
