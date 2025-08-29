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
# BASE FORM CLASSES FOR CONSISTENCY
# =====================================

class InventoryBaseForm(forms.ModelForm):
    """
    Base form class for all inventory forms.
    
    Provides consistent styling, validation patterns, and AJAX support.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Apply consistent CSS classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 3})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.DateInput):
                field.widget.attrs.update({
                    'class': 'form-control',
                    'type': 'date'
                })
    
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

class EntityManagementForm(InventoryBaseForm):
    """
    Base form for entity management (categories, brands, suppliers, etc.)
    
    Provides common fields and validation patterns for business entities.
    """
    
    class Meta:
        abstract = True
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Common field configurations
        if 'name' in self.fields:
            self.fields['name'].widget.attrs.update({
                'placeholder': f'Enter {self._meta.model._meta.verbose_name.lower()} name...'
            })
        
        if 'description' in self.fields:
            self.fields['description'].widget.attrs.update({
                'placeholder': f'Optional description for this {self._meta.model._meta.verbose_name.lower()}...'
            })
    
    def clean_name(self):
        """Validate name uniqueness and format"""
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            
            # Check for uniqueness
            if 'name' in self.fields:
                queryset = self._meta.model.objects.filter(name__iexact=name)
                if self.instance.pk:
                    queryset = queryset.exclude(pk=self.instance.pk)
                
                if queryset.exists():
                    raise ValidationError(
                        f'A {self._meta.model._meta.verbose_name.lower()} with this name already exists.'
                    )
        
        return name

class SearchFormBase(forms.Form):
    """
    Base form for search and filtering operations.
    
    Provides common search fields and patterns.
    """
    
    search = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search...'
        })
    )
    
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Customize search placeholder based on context
        model_name = getattr(self, 'search_model_name', 'items')
        self.fields['search'].widget.attrs['placeholder'] = f'Search {model_name}...'

class BulkOperationForm(forms.Form):
    """
    Base form for bulk operations across different entities.
    
    Provides consistent bulk operation patterns.
    """
    
    ACTION_CHOICES = []  # To be overridden by subclasses
    
    action = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    confirm_action = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I confirm I want to perform this bulk operation'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['action'].choices = self.ACTION_CHOICES
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not cleaned_data.get('confirm_action'):
            raise ValidationError('You must confirm the bulk operation.')
        
        return cleaned_data

# =====================================
# SPECIALIZED FORM MIXINS
# =====================================

class PricingFieldsMixin:
    """Mixin for forms that include pricing fields"""
    
    def add_pricing_fields(self):
        """Add common pricing fields"""
        self.fields['cost_price'] = forms.DecimalField(
            max_digits=10, 
            decimal_places=2,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            })
        )
        
        self.fields['selling_price'] = forms.DecimalField(
            max_digits=10, 
            decimal_places=2,
            required=False,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            })
        )

class StockFieldsMixin:
    """Mixin for forms that include stock-related fields"""
    
    def add_stock_fields(self):
        """Add common stock fields"""
        self.fields['current_stock'] = forms.IntegerField(
            min_value=0,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            })
        )
        
        self.fields['reorder_level'] = forms.IntegerField(
            min_value=0,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            })
        )

class ContactFieldsMixin:
    """Mixin for forms that include contact information"""
    
    def add_contact_fields(self):
        """Add common contact fields"""
        self.fields['email'] = forms.EmailField(
            required=False,
            widget=forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            })
        )
        
        self.fields['phone'] = forms.CharField(
            max_length=20,
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1234567890'
            })
        )
        
        self.fields['website'] = forms.URLField(
            required=False,
            widget=forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com'
            })
        )

# =====================================
# UTILITY FUNCTIONS FOR FORMS
# =====================================

def get_active_choices(model_class, empty_label="All"):
    """Get choices for active records of a model"""
    queryset = model_class.objects.filter(is_active=True).order_by('name')
    choices = [('', empty_label)]
    choices.extend([(obj.pk, str(obj)) for obj in queryset])
    return choices

def validate_unique_field(instance, field_name, value, error_message=None):
    """Validate field uniqueness across model instances"""
    if not value:
        return value
    
    queryset = instance.__class__.objects.filter(**{f"{field_name}__iexact": value})
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    
    if queryset.exists():
        error_message = error_message or f"A record with this {field_name} already exists."
        raise ValidationError(error_message)
    
    return value

def clean_website_url(url):
    """Standardize website URL format"""
    if url and not url.startswith(('http://', 'https://')):
        return f'https://{url}'
    return url

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

class CategoryForm(EntityManagementForm):
    """Category creation and editing form with hierarchical support"""
    
    class Meta:
        model = Category
        fields = ['name', 'description', 'parent', 'is_active']
    
    parent = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label='No Parent (Top Level)',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_parent(self):
        """Prevent circular references in category hierarchy"""
        parent = self.cleaned_data.get('parent')
        
        if parent and self.instance.pk:
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

class BrandForm(EntityManagementForm):
    """Brand creation and editing form"""
    
    class Meta:
        model = Brand
        fields = ['name', 'description', 'is_active']

# =====================================
# SUPPLIER MANAGEMENT FORMS
# =====================================

class SupplierForm(EntityManagementForm, ContactFieldsMixin):
    """Comprehensive supplier management form"""
    
    class Meta:
        model = Supplier
        fields = [
            'name', 'supplier_code', 'supplier_type','email', 'phone',
            'website', 'contact_person', 'whatsapp', 'is_preferred',
            'is_active', 'address_line_1', 'address_line_2', 'city',
            'state_province', 'postal_code', 'country', 'currency',
            'payment_terms', 'typical_lead_time_days', 'minimum_order_value',
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_contact_fields()
        
        # Customize specific fields
        self.fields['supplier_code'].widget.attrs.update({
            'placeholder': 'Unique supplier code (auto-generated if empty)'
        })
        
        self.fields['payment_terms'].widget.attrs.update({
            'placeholder': 'e.g., Net 30, COD, etc.'
        })
        
        self.fields['typical_lead_time_days'].widget.attrs.update({
            'min': '0', 'max': '365'
        })
        
        # Address field customizations
        self.fields['address_line_1'].widget.attrs.update({
            'placeholder': 'Street address'
        })
        
        self.fields['address_line_2'].widget.attrs.update({
            'placeholder': 'Apartment, suite, etc. (optional)'
        })
        
        self.fields['city'].widget.attrs.update({
            'placeholder': 'City'
        })
        
        self.fields['state_province'].widget.attrs.update({
            'placeholder': 'State/Province (optional)'
        })
        
        self.fields['postal_code'].widget.attrs.update({
            'placeholder': 'Postal/ZIP code'
        })
    
    def clean_supplier_code(self):
        """Generate unique supplier code if not provided"""
        code = self.cleaned_data.get('supplier_code')
        
        if not code:
            # Auto-generate from name
            name = self.cleaned_data.get('name', '')
            code = ''.join(word[:3].upper() for word in name.split()[:2])
            
            # Ensure uniqueness
            base_code = code
            counter = 1
            while Supplier.objects.filter(supplier_code=code).exclude(
                pk=self.instance.pk if self.instance else None
            ).exists():
                code = f"{base_code}{counter:02d}"
                counter += 1
        
        return validate_unique_field(
            self.instance, 'supplier_code', code,
            'A supplier with this code already exists.'
        )
    
    def clean_email(self):
        """Validate email format and uniqueness"""
        email = self.cleaned_data.get('email')
        if email:
            return validate_unique_field(
                self.instance, 'email', email,
                'A supplier with this email already exists.'
            )
        return email
    
    def clean_website(self):
        """Ensure website URL is properly formatted"""
        return clean_website_url(self.cleaned_data.get('website'))

# =====================================
# LOCATION MANAGEMENT FORMS
# =====================================

class LocationForm(EntityManagementForm, ContactFieldsMixin):
    """Location management form for multi-location inventory"""
    
    class Meta:
        model = Location
        fields = [
            'name', 'description', 'location_type', 'address',
            'phone', 'email', 'manager_name', 'is_active'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_contact_fields()
        
        self.fields['manager_name'].widget.attrs.update({
            'placeholder': 'Location manager name'
        })

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

class ProductForm(InventoryBaseForm, PricingFieldsMixin, StockFieldsMixin):
    """Comprehensive product management form"""
    
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'description', 'category', 'brand', 'supplier',
            'cost_price', 'selling_price', 'current_stock', 'reorder_level',
            'unit_of_measure', 'weight', 'dimensions', 'is_active'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_pricing_fields()
        self.add_stock_fields()
        
        # Customize specific fields
        self.fields['sku'].widget.attrs.update({
            'placeholder': 'Unique product code (auto-generated if empty)'
        })
        
        self.fields['dimensions'].widget.attrs.update({
            'placeholder': 'L x W x H (optional)'
        })
    
    def clean_sku(self):
        """Generate unique SKU if not provided"""
        sku = self.cleaned_data.get('sku')
        
        if not sku:
            # Auto-generate from name and category
            name = self.cleaned_data.get('name', '')
            category = self.cleaned_data.get('category')
            
            if category:
                sku = f"{category.name[:3].upper()}-{name[:6].upper()}"
            else:
                sku = name[:10].upper()
            
            # Remove spaces and special characters
            sku = ''.join(c for c in sku if c.isalnum() or c == '-')
            
            # Ensure uniqueness
            base_sku = sku
            counter = 1
            while Product.objects.filter(sku=sku).exclude(
                pk=self.instance.pk if self.instance else None
            ).exists():
                sku = f"{base_sku}-{counter:03d}"
                counter += 1
        
        return validate_unique_field(
            self.instance, 'sku', sku,
            'A product with this SKU already exists.'
        )

# =====================================
# STOCK MANAGEMENT FORMS
# =====================================

class StockAdjustmentForm(InventoryBaseForm):
    """Stock adjustment form with validation"""
    
    adjustment_type = forms.ChoiceField(
        choices=[
            ('increase', 'Increase Stock'),
            ('decrease', 'Decrease Stock'),
            ('set_to', 'Set Stock To')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1'
        })
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for adjustment...'
        })
    )
    
    class Meta:
        model = StockMovement
        fields = ['adjustment_type', 'quantity', 'reason']

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

class ProductSearchForm(SearchFormBase):
    """Advanced product search form"""
    
    search_model_name = 'products'
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label='All Categories',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label='All Suppliers',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    stock_status = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    min_price = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Min price'
        })
    )
    
    max_price = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Max price'
        })
    )

class SupplierSearchForm(SearchFormBase):
    """Advanced supplier search form"""
    
    search_model_name = 'suppliers'
    
    supplier_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(Supplier.SUPPLIER_TYPES) if hasattr(Supplier, 'SUPPLIER_TYPES') else [],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    country = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Country'
        })
    )
    
    is_preferred = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Preferred'), ('false', 'Standard')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
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

# =====================================
# BULK OPERATION FORMS
# =====================================

class CategoryBulkUpdateForm(BulkOperationForm):
    """Bulk update form for categories"""
    
    ACTION_CHOICES = [
        ('update_markup', 'Update Default Markup'),
        ('activate', 'Activate Categories'),
        ('deactivate', 'Deactivate Categories'),
    ]
    
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=True
    )
    
    new_markup_percentage = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'update_markup' and not cleaned_data.get('new_markup_percentage'):
            raise ValidationError('Markup percentage is required for markup updates.')
        
        return cleaned_data

class ProductBulkUpdateForm(BulkOperationForm):
    """Bulk update form for products"""
    
    ACTION_CHOICES = [
        ('update_prices', 'Update Prices'),
        ('update_category', 'Update Category'),
        ('update_supplier', 'Update Supplier'),
        ('activate', 'Activate Products'),
        ('deactivate', 'Deactivate Products'),
    ]
    
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=True
    )
    
    price_adjustment_type = forms.ChoiceField(
        choices=[
            ('percentage', 'Percentage Increase/Decrease'),
            ('fixed_amount', 'Fixed Amount Increase/Decrease'),
            ('set_price', 'Set Fixed Price')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    price_adjustment_value = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        })
    )
    
    new_category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    new_supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        
        if action == 'update_prices':
            if not cleaned_data.get('price_adjustment_type') or not cleaned_data.get('price_adjustment_value'):
                raise ValidationError('Price adjustment type and value are required for price updates.')
        
        elif action == 'update_category' and not cleaned_data.get('new_category'):
            raise ValidationError('New category is required for category updates.')
        
        elif action == 'update_supplier' and not cleaned_data.get('new_supplier'):
            raise ValidationError('New supplier is required for supplier updates.')
        
        return cleaned_data
