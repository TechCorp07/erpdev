# inventory/forms.py - Comprehensive Inventory Management Forms

"""
Django Forms for Inventory Management

Key Features:
1. Dynamic product attributes based on component family
2. Advanced cost calculation with real-time overhead computation
3. Multi-currency support with exchange rate integration
4. Intelligent field validation and business logic
5. Dynamic form generation for configurable attributes
6. Bulk operations support
7. Integration with barcode/QR systems
"""

import json
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal
from django.utils import timezone
import re

from .models import (
    Brand, Category, ComponentFamily, Currency, OverheadFactor, ProductAttributeDefinition, StorageBin, StorageLocation, Supplier, Location, Product, StockLevel, StockMovement,
    StockTake, StockTakeItem, PurchaseOrder, PurchaseOrderItem, ReorderAlert, SupplierCountry
)

# =====================================
# DYNAMIC ATTRIBUTE FORMS
# =====================================

class DynamicAttributeFormMixin:
    """Mixin to add dynamic attributes to product forms"""
    
    def __init__(self, *args, **kwargs):
        self.component_family = kwargs.pop('component_family', None)
        super().__init__(*args, **kwargs)
        
        if self.component_family:
            self.add_dynamic_attributes()
        elif self.instance and self.instance.pk and self.instance.component_family:
            self.component_family = self.instance.component_family
            self.add_dynamic_attributes()
    
    def add_dynamic_attributes(self):
        """Add dynamic attribute fields based on component family"""
        if not self.component_family:
            return
        
        attribute_definitions = self.component_family.all_attributes
        
        for attr_def in attribute_definitions:
            field_name = f"attr_{attr_def.id}"
            
            # Create appropriate field type
            if attr_def.field_type == 'text':
                field = forms.CharField(
                    required=attr_def.is_required,
                    initial=attr_def.default_value,
                    help_text=attr_def.help_text,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
                
            elif attr_def.field_type == 'number':
                field = forms.IntegerField(
                    required=attr_def.is_required,
                    initial=int(attr_def.default_value) if attr_def.default_value else None,
                    help_text=attr_def.help_text,
                    widget=forms.NumberInput(attrs={'class': 'form-control'})
                )
                if attr_def.min_value:
                    field.widget.attrs['min'] = int(attr_def.min_value)
                if attr_def.max_value:
                    field.widget.attrs['max'] = int(attr_def.max_value)
                    
            elif attr_def.field_type == 'decimal':
                field = forms.DecimalField(
                    required=attr_def.is_required,
                    initial=Decimal(attr_def.default_value) if attr_def.default_value else None,
                    help_text=attr_def.help_text,
                    max_digits=15,
                    decimal_places=6,
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'})
                )
                if attr_def.min_value:
                    field.widget.attrs['min'] = float(attr_def.min_value)
                if attr_def.max_value:
                    field.widget.attrs['max'] = float(attr_def.max_value)
                    
            elif attr_def.field_type == 'choice':
                choices = [('', '-- Select --')]
                if attr_def.choice_options:
                    choices.extend([(opt, opt) for opt in attr_def.choice_options])
                
                field = forms.ChoiceField(
                    choices=choices,
                    required=attr_def.is_required,
                    initial=attr_def.default_value,
                    help_text=attr_def.help_text,
                    widget=forms.Select(attrs={'class': 'form-control'})
                )
                
            elif attr_def.field_type == 'boolean':
                field = forms.BooleanField(
                    required=attr_def.is_required,
                    initial=attr_def.default_value == 'True',
                    help_text=attr_def.help_text,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
                
            elif attr_def.field_type == 'url':
                field = forms.URLField(
                    required=attr_def.is_required,
                    initial=attr_def.default_value,
                    help_text=attr_def.help_text,
                    widget=forms.URLInput(attrs={'class': 'form-control'})
                )
                
            elif attr_def.field_type == 'email':
                field = forms.EmailField(
                    required=attr_def.is_required,
                    initial=attr_def.default_value,
                    help_text=attr_def.help_text,
                    widget=forms.EmailInput(attrs={'class': 'form-control'})
                )
            else:
                # Default to text field
                field = forms.CharField(
                    required=attr_def.is_required,
                    initial=attr_def.default_value,
                    help_text=attr_def.help_text,
                    widget=forms.TextInput(attrs={'class': 'form-control'})
                )
            
            # Add validation pattern if specified
            if attr_def.validation_pattern:
                field.validators.append(
                    lambda value, pattern=attr_def.validation_pattern: self.validate_pattern(value, pattern)
                )
            
            field.label = attr_def.name
            self.fields[field_name] = field
            
            # Set initial value from instance if editing
            if self.instance and self.instance.pk:
                current_value = self.instance.get_attribute_value(attr_def.name)
                if current_value:
                    self.fields[field_name].initial = current_value
    
    def validate_pattern(self, value, pattern):
        """Validate field value against regex pattern"""
        if value and not re.match(pattern, str(value)):
            raise ValidationError(f"Value does not match required pattern: {pattern}")
    
    def save_dynamic_attributes(self, product):
        """Save dynamic attribute values to product"""
        if not self.component_family:
            return
        
        attribute_definitions = self.component_family.all_attributes
        dynamic_attributes = {}
        
        for attr_def in attribute_definitions:
            field_name = f"attr_{attr_def.id}"
            if field_name in self.cleaned_data:
                value = self.cleaned_data[field_name]
                if value is not None and value != '':
                    dynamic_attributes[attr_def.name] = str(value)
        
        product.dynamic_attributes = dynamic_attributes
        product.save(update_fields=['dynamic_attributes'])

# =====================================
# SYSTEM CONFIGURATION FORMS
# =====================================

class CurrencyForm(forms.ModelForm):
    """Form for managing currencies and exchange rates"""
    
    class Meta:
        model = Currency
        fields = [
            'code', 'name', 'symbol', 'exchange_rate_to_usd',
            'auto_update_enabled', 'api_source', 'is_active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'USD, EUR, CNY'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'US Dollar'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '$, €, ¥'}),
            'exchange_rate_to_usd': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'auto_update_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'api_source': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_code(self):
        code = self.cleaned_data.get('code', '').upper()
        if len(code) != 3:
            raise ValidationError('Currency code must be exactly 3 characters')
        return code
    
    def clean_exchange_rate_to_usd(self):
        rate = self.cleaned_data.get('exchange_rate_to_usd')
        if rate and rate <= 0:
            raise ValidationError('Exchange rate must be positive')
        return rate


class OverheadFactorForm(forms.ModelForm):
    """Form for configuring overhead factors"""
    
    class Meta:
        model = OverheadFactor
        fields = [
            'name', 'description', 'calculation_type', 'fixed_amount',
            'percentage_rate', 'applies_to_categories', 'applies_to_suppliers',
            'display_order', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Rent, Electricity, Bank Charges'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'calculation_type': forms.Select(attrs={'class': 'form-control'}),
            'fixed_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'percentage_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'applies_to_categories': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '6'}),
            'applies_to_suppliers': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '6'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['applies_to_categories'].queryset = Category.objects.filter(is_active=True)
        self.fields['applies_to_suppliers'].queryset = Supplier.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        calculation_type = cleaned_data.get('calculation_type')
        fixed_amount = cleaned_data.get('fixed_amount')
        percentage_rate = cleaned_data.get('percentage_rate')
        
        if calculation_type in ['fixed_per_item', 'fixed_per_order']:
            if not fixed_amount or fixed_amount <= 0:
                self.add_error('fixed_amount', 'Fixed amount is required for this calculation type')
        else:
            if not percentage_rate or percentage_rate <= 0:
                self.add_error('percentage_rate', 'Percentage rate is required for this calculation type')
        
        return cleaned_data

class ProductAttributeDefinitionForm(forms.ModelForm):
    """Form for defining dynamic product attributes"""
    
    class Meta:
        model = ProductAttributeDefinition
        fields = [
            'name', 'field_type', 'component_families', 'is_required',
            'default_value', 'help_text', 'choice_options',
            'min_value', 'max_value', 'validation_pattern',
            'display_order', 'show_in_listings', 'show_in_search', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Voltage Rating, Package Type'}),
            'field_type': forms.Select(attrs={'class': 'form-control'}),
            'component_families': forms.SelectMultiple(attrs={'class': 'form-control', 'size': '6'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_value': forms.TextInput(attrs={'class': 'form-control'}),
            'help_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Help text for users'}),
            'choice_options': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': '["Option1", "Option2", "Option3"]'}),
            'min_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'max_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'validation_pattern': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Regex pattern'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'show_in_listings': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_in_search': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['component_families'].queryset = ComponentFamily.objects.filter(is_active=True)
    
    def clean_choice_options(self):
        choice_options = self.cleaned_data.get('choice_options')
        field_type = self.cleaned_data.get('field_type')
        
        if field_type == 'choice' and choice_options:
            try:
                options = json.loads(choice_options)
                if not isinstance(options, list):
                    raise ValidationError('Choice options must be a JSON list')
                return options
            except json.JSONDecodeError:
                raise ValidationError('Invalid JSON format for choice options')
        
        return choice_options if choice_options else []

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
            'email', 'phone', 'whatsapp', 'website',
            'address_line_1', 'address_line_2', 'city', 'state_province',
            'postal_code', 'country',
            'payment_terms', 'currency', 'minimum_order_value',
            'typical_lead_time_days', 'reliability_rating',
            'preferred_shipping_method', 'rating',
            'is_active', 'notes'
        ]
        widgets = {
            'reliability_rating': forms.NumberInput(attrs={
                'step': '0.1', 'min': '1', 'max': '10'
            }),
            'minimum_order_value': forms.NumberInput(attrs={
                'step': '0.01', 'min': '0'
            }),
            'typical_lead_time_days': forms.NumberInput(attrs={
                'min': '1', 'max': '365'
            }),
            'rating': forms.NumberInput(attrs={
                'min': '1', 'max': '5'
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
        self.fields['typical_lead_time_days'].help_text = 'Typical lead time in days'
        self.fields['rating'].help_text = 'Supplier rating (1-5 stars)'
        
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
# SEARCH AND FILTER FORMS
# =====================================

class AdvancedProductSearchForm(forms.Form):
    """Advanced search form with electronics-specific filters"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, SKU, part number, description...',
            'autocomplete': 'off'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    component_family = forms.ModelChoiceField(
        queryset=ComponentFamily.objects.filter(is_active=True),
        required=False,
        empty_label='All Component Families',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    brand = forms.ModelChoiceField(
        queryset=Brand.objects.filter(is_active=True),
        required=False,
        empty_label='All Brands',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label='All Suppliers',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    supplier_country = forms.ModelChoiceField(
        queryset=SupplierCountry.objects.filter(is_active=True),
        required=False,
        empty_label='All Countries',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    product_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(Product.PRODUCT_TYPES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    quality_grade = forms.ChoiceField(
        choices=[('', 'All Grades')] + [
            ('consumer', 'Consumer Grade'),
            ('industrial', 'Industrial Grade'),
            ('automotive', 'Automotive Grade'),
            ('military', 'Military Grade'),
            ('space', 'Space Grade'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    stock_status = forms.ChoiceField(
        choices=[
            ('', 'All Stock Levels'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
            ('needs_reorder', 'Needs Reorder')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    price_range_min = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min Price',
            'step': '0.01'
        })
    )
    
    price_range_max = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Price',
            'step': '0.01'
        })
    )
    
    markup_range_min = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min Markup %',
            'step': '0.01'
        })
    )
    
    markup_range_max = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Markup %',
            'step': '0.01'
        })
    )
    
    # Special characteristics
    is_hazardous = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Hazardous materials only"
    )
    
    requires_esd_protection = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="ESD sensitive only"
    )
    
    is_temperature_sensitive = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Temperature sensitive only"
    )
    
    has_datasheet = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Has datasheet only"
    )
    
    # Dynamic attribute search - these will be added dynamically
    def __init__(self, *args, **kwargs):
        self.component_family = kwargs.pop('component_family', None)
        super().__init__(*args, **kwargs)
        
        if self.component_family:
            self.add_attribute_search_fields()
    
    def add_attribute_search_fields(self):
        """Add search fields for dynamic attributes"""
        if not self.component_family:
            return
        
        # Add search fields for commonly searched attributes
        searchable_attrs = self.component_family.attribute_definitions.filter(
            show_in_search=True,
            is_active=True
        )
        
        for attr_def in searchable_attrs:
            field_name = f"attr_search_{attr_def.id}"
            
            if attr_def.field_type in ['text', 'number', 'decimal']:
                field = forms.CharField(
                    required=False,
                    widget=forms.TextInput(attrs={
                        'class': 'form-control',
                        'placeholder': f'Search {attr_def.name}'
                    })
                )
            elif attr_def.field_type == 'choice':
                choices = [('', f'All {attr_def.name}')]
                if attr_def.choice_options:
                    choices.extend([(opt, opt) for opt in attr_def.choice_options])
                
                field = forms.ChoiceField(
                    choices=choices,
                    required=False,
                    widget=forms.Select(attrs={'class': 'form-control'})
                )
            else:
                continue  # Skip other field types for search
            
            field.label = f"{attr_def.name}"
            self.fields[field_name] = field

# =====================================
# BULK OPERATIONS FORMS
# =====================================

class BulkCostUpdateForm(forms.Form):
    """Form for bulk updating product costs and pricing"""
    
    UPDATE_TYPES = [
        ('exchange_rate', 'Apply Exchange Rate Change'),
        ('shipping_cost', 'Update Shipping Costs'),
        ('duty_percentage', 'Update Customs Duty %'),
        ('markup_percentage', 'Update Markup %'),
        ('selling_price_increase', 'Increase Selling Price by %'),
        ('overhead_recalculation', 'Recalculate Overhead Costs'),
    ]
    
    update_type = forms.ChoiceField(
        choices=UPDATE_TYPES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='markup_percentage'
    )
    
    value = forms.DecimalField(
        max_digits=15,
        decimal_places=6,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        help_text="Enter the new value or percentage change"
    )
    
    # Filters for which products to update
    apply_to_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    apply_to_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label="All Suppliers",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    apply_to_brand = forms.ModelChoiceField(
        queryset=Brand.objects.filter(is_active=True),
        required=False,
        empty_label="All Brands",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    apply_to_currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        required=False,
        empty_label="All Currencies",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="For exchange rate updates, select the currency to update"
    )
    
    preview_only = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Preview changes before applying (recommended)"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        update_type = cleaned_data.get('update_type')
        value = cleaned_data.get('value')
        
        if update_type == 'exchange_rate' and not cleaned_data.get('apply_to_currency'):
            self.add_error('apply_to_currency', 'Currency selection is required for exchange rate updates')
        
        if value is not None:
            if update_type in ['markup_percentage', 'selling_price_increase'] and value < 0:
                self.add_error('value', 'Percentage values cannot be negative')
            
            if update_type == 'exchange_rate' and value <= 0:
                self.add_error('value', 'Exchange rate must be positive')
        
        return cleaned_data

class ReorderListGenerationForm(forms.Form):
    """Form for generating customized reorder lists"""
    
    PRIORITY_CHOICES = [
        ('', 'All Priorities'),
        ('critical', 'Critical (Out of Stock)'),
        ('high', 'High (Very Low Stock)'),
        ('medium', 'Medium (Low Stock)'),
    ]
    
    FORMAT_CHOICES = [
        ('csv', 'CSV File'),
        ('excel', 'Excel File'),
        ('pdf', 'PDF Report'),
    ]
    
    # Filters
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label="All Suppliers",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    supplier_country = forms.ModelChoiceField(
        queryset=SupplierCountry.objects.filter(is_active=True),
        required=False,
        empty_label="All Countries",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Output options
    output_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        initial='csv',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    group_by_supplier = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Group products by supplier for easier ordering"
    )
    
    include_supplier_contact = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include supplier contact information"
    )
    
    include_cost_analysis = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include detailed cost breakdown (confidential)"
    )
    
    calculate_optimal_quantities = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Calculate optimal order quantities based on EOQ"
    )

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
    # Custom fields for better UX
    calculate_costs = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Automatically calculate total costs and markup"
    )
    
    target_markup_percentage = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text="Target markup percentage for automatic pricing"
    )
    
    class Meta:
        model = Product
        fields = [
            # Basic information
            'name', 'sku', 'barcode', 'description', 'short_description',
            # Categorization  
            'category', 'supplier', 'product_type',
            # Specifications
            'brand', 'model_number', 'manufacturer_part_number', 'supplier_sku',
            # Physical attributes
            'weight', 'dimensions',
            # Cost structure
            'cost_price', 'selling_price', 'currency',
            # Stock management
            'current_stock', 'reserved_stock', 'available_stock',
            'reorder_level', 'reorder_quantity', 'max_stock_level',
            'supplier_lead_time_days', 'supplier_minimum_order_quantity',
            # Quote settings
            'quote_description', 'minimum_quote_quantity', 
            'bulk_discount_threshold', 'bulk_discount_percentage',
            # Status flags
            'is_active', 'is_quotable', 'is_serialized', 'requires_quality_check',
            # SEO
            'meta_title', 'meta_description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descriptive product name'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'BT-2024-001'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Barcode number'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'short_description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief description'}),
            'quote_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            
            # Dropdowns
            'category': forms.Select(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'product_type': forms.Select(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            
            # Text fields
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'model_number': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer_part_number': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'dimensions': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'L x W x H in cm'}),
            
            # Numeric fields
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            # Stock fields
            'current_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reserved_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'available_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'max_stock_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'supplier_lead_time_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'supplier_minimum_order_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            
            # Quote fields
            'minimum_quote_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'bulk_discount_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'bulk_discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            
            # SEO fields
            'meta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            
            # Boolean fields
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_quotable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_serialized': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_quality_check': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set up currency choices (matching your existing choices)
        CURRENCY_CHOICES = [
            ('USD', 'US Dollar'),
            ('ZWG', 'Zimbabwe Gold'),
            ('ZAR', 'South African Rand'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
        ]
        self.fields['currency'].choices = CURRENCY_CHOICES
        
        # Make key fields required
        self.fields['category'].required = True
        self.fields['supplier'].required = True
        self.fields['cost_price'].required = True
        self.fields['selling_price'].required = True
        
        # Add help texts
        self.fields['sku'].help_text = 'Unique product identifier'
        self.fields['weight'].help_text = 'Weight in kilograms'
        self.fields['reorder_level'].help_text = 'Minimum stock level before reordering'
        self.fields['available_stock'].help_text = 'Calculated automatically (current - reserved)'
        self.fields['quote_description'].help_text = 'Different description for quotes (optional)'
        self.fields['bulk_discount_percentage'].help_text = 'Discount % for bulk orders'
    
    def clean_sku(self):
        """Ensure SKU is unique"""
        sku = self.cleaned_data.get('sku')
        
        if sku:
            existing = Product.objects.filter(sku=sku)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('A product with this SKU already exists.')
        
        return sku
    
    def clean(self):
        """Additional validation"""
        cleaned_data = super().clean()
        cost_price = cleaned_data.get('cost_price')
        selling_price = cleaned_data.get('selling_price')
        current_stock = cleaned_data.get('current_stock')
        reserved_stock = cleaned_data.get('reserved_stock')
        bulk_discount_threshold = cleaned_data.get('bulk_discount_threshold')
        bulk_discount_percentage = cleaned_data.get('bulk_discount_percentage')
        
        # Validate pricing
        if cost_price and selling_price:
            if selling_price < cost_price:
                self.add_error('selling_price', 'Selling price should not be less than cost price.')
        
        # Validate stock levels
        if current_stock is not None and reserved_stock is not None:
            if reserved_stock > current_stock:
                self.add_error('reserved_stock', 'Reserved stock cannot exceed current stock.')
                
            # Auto-calculate available stock
            cleaned_data['available_stock'] = current_stock - reserved_stock
        
        # Validate bulk discount
        if bulk_discount_threshold and bulk_discount_percentage:
            if bulk_discount_percentage < 0 or bulk_discount_percentage > 100:
                self.add_error('bulk_discount_percentage', 'Discount percentage must be between 0 and 100.')
        
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
        ('transfer', 'Transfer between locations'),
    ]
    
    REASON_CHOICES = [
        ('stock_take', 'Stock Take Adjustment'),
        ('damage', 'Damaged Goods'),
        ('theft', 'Theft/Loss'),
        ('customer_return', 'Customer Return'),
        ('supplier_return', 'Return to Supplier'),
        ('promotion', 'Promotional Use'),
        ('sample', 'Sample/Demo'),
        ('correction', 'Data Correction'),
        ('other', 'Other'),
    ]
    
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    storage_bin = forms.ModelChoiceField(
            queryset=StorageBin.objects.filter(is_active=True),
            required=False,
            empty_label="No specific bin",
            widget=forms.Select(attrs={'class': 'form-control'})
    )
    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0'})
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )    
    # For transfers
    transfer_to_location = forms.ModelChoiceField(
        queryset=Location.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Required for transfer adjustments"
    )
    
    transfer_to_bin = forms.ModelChoiceField(
        queryset=StorageBin.objects.filter(is_active=True),
        required=False,
        empty_label="No specific bin",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    notes = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Additional notes about this adjustment"
    )
    
    reference_document = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PO, Invoice, Stock Take #'}),
        help_text="Reference document number"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default location
        default_location = Location.objects.filter(is_default=True).first()
        if default_location:
            self.fields['location'].initial = default_location
    
    def clean(self):
        cleaned_data = super().clean()
        
        product = cleaned_data.get('product')
        adjustment_type = cleaned_data.get('adjustment_type')
        location = cleaned_data.get('location')
        quantity = cleaned_data.get('quantity')
        
        # Validate transfer fields
        if adjustment_type == 'transfer':
            transfer_to = cleaned_data.get('transfer_to_location')
            if not transfer_to:
                self.add_error('transfer_to_location', 'Transfer destination is required')
            elif transfer_to == location:
                self.add_error('transfer_to_location', 'Cannot transfer to the same location')
        
        # Validate sufficient stock for subtract operations
        if adjustment_type == 'subtract' and product and location and quantity:
            current_stock = product.get_stock_at_location(location)
            if quantity > current_stock:
                self.add_error('quantity', f'Cannot subtract {quantity} from current stock of {current_stock}')
        
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
