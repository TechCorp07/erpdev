from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import Quote, QuoteItem, QuoteTemplate
from crm.models import Client
from inventory.models import Product, Supplier

class QuoteForm(forms.ModelForm):
    """
    The main quote creation form. This form is designed to be intelligent -
    it knows about your client preferences, business rules, and will 
    pre-populate sensible defaults to speed up quote creation.
    """
    
    class Meta:
        model = Quote
        fields = [
            'client', 'title', 'description', 'priority', 
            'payment_terms', 'delivery_terms', 'validity_date',
            'discount_percentage', 'tax_rate', 'currency'
        ]
        
        widgets = {
            'client': forms.Select(attrs={
                'class': 'form-control',
                'data-live-search': 'true',  # Enable searchable dropdown
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description of this quote (e.g., Office Computer Setup)',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Detailed description or special notes for this quote...',
            }),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'payment_terms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '365',
                'step': '1',
            }),
            'delivery_terms': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Delivered to client premises, FOB Harare',
            }),
            'validity_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'discount_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
            }),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '100',
                'step': '0.01',
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        This initialization method is where the magic happens. It makes the form
        intelligent by setting smart defaults based on business rules and client preferences.
        """
        user = kwargs.pop('user', None)  # Current user creating the quote
        client = kwargs.pop('client', None)  # Pre-selected client (if any)
        
        super().__init__(*args, **kwargs)
        
        # Make client field searchable and limit to active clients
        self.fields['client'].queryset = Client.objects.filter(
            status__in=['prospect', 'client']
        ).order_by('name')
        
        # If we're editing an existing quote, don't override with defaults
        if not self.instance.pk:
            # Set intelligent defaults for new quotes
            self.fields['validity_date'].initial = (
                timezone.now().date() + timedelta(days=30)
            )
            self.fields['tax_rate'].initial = Decimal('15.00')  # Zimbabwe VAT
            
            # If client is pre-selected, use their preferences
            if client:
                self.fields['client'].initial = client
                self.fields['payment_terms'].initial = client.payment_terms
                self.fields['currency'].initial = client.currency_preference
                self.fields['discount_percentage'].initial = client.default_markup_percentage
                
                # Set validity based on client's preference
                if hasattr(client, 'quote_validity_days'):
                    validity_days = client.quote_validity_days or 30
                    self.fields['validity_date'].initial = (
                        timezone.now().date() + timedelta(days=validity_days)
                    )
        
        # Set user as assigned_to if provided
        if user:
            self.instance.created_by = user
            self.instance.assigned_to = user
    
    def clean_validity_date(self):
        """
        Business rule validation: quotes can't expire in the past or too far in the future.
        This prevents common mistakes and enforces business policies.
        """
        validity_date = self.cleaned_data['validity_date']
        
        if validity_date <= timezone.now().date():
            raise forms.ValidationError(
                "Quote validity date must be in the future."
            )
        
        # Don't allow quotes valid for more than 6 months
        max_date = timezone.now().date() + timedelta(days=180)
        if validity_date > max_date:
            raise forms.ValidationError(
                "Quote validity cannot exceed 6 months from today."
            )
        
        return validity_date
    
    def clean_discount_percentage(self):
        """
        Business rule: large discounts need approval.
        This integrates with your permission system.
        """
        discount = self.cleaned_data['discount_percentage']
        
        # If discount is over 15%, flag for approval
        if discount > 15:
            if not hasattr(self.instance, '_requires_approval'):
                self.instance._requires_approval = True
        
        return discount

class QuoteItemForm(forms.ModelForm):
    """
    Form for adding individual items to quotes. This form is designed to be used
    in dynamic JavaScript contexts (AJAX) for building quotes interactively.
    """
    
    # Custom field for product search
    product_search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search products...',
            'data-toggle': 'product-search',
        }),
        help_text="Type to search for products by name or SKU"
    )
    
    class Meta:
        model = QuoteItem
        fields = [
            'product', 'description', 'detailed_specs', 
            'quantity', 'unit_price', 'source_type', 
            'supplier', 'supplier_lead_time', 'estimated_delivery', 'notes'
        ]
        
        widgets = {
            'product': forms.Select(attrs={
                'class': 'form-control',
                'data-live-search': 'true',
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Product/service description',
            }),
            'detailed_specs': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Technical specifications, model numbers, etc.',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'step': '1',
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
            }),
            'source_type': forms.Select(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'supplier_lead_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '1',
            }),
            'estimated_delivery': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Internal notes about this item',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show quotable products
        self.fields['product'].queryset = Product.objects.filter(
            is_quotable=True
        ).order_by('name')
        
        # Only show active suppliers
        self.fields['supplier'].queryset = Supplier.objects.filter(
            is_active=True
        ).order_by('name')
        
        # Make supplier optional initially
        self.fields['supplier'].required = False
    
    def clean(self):
        """
        Cross-field validation to ensure business rules are followed.
        """
        cleaned_data = super().clean()
        source_type = cleaned_data.get('source_type')
        supplier = cleaned_data.get('supplier')
        product = cleaned_data.get('product')
        unit_price = cleaned_data.get('unit_price')
        
        # If source is from supplier, supplier must be specified
        if source_type in ['order', 'direct'] and not supplier:
            raise forms.ValidationError(
                "Supplier must be specified for supplier-sourced items."
            )
        
        # If product is selected, validate pricing against cost
        if product and unit_price:
            if hasattr(product, 'cost_price') and product.cost_price > 0:
                if unit_price < product.cost_price:
                    # This is a warning, not an error - sometimes you sell at cost
                    self.add_error('unit_price', 
                        f"Warning: Price (${unit_price}) is below cost (${product.cost_price})"
                    )
        
        return cleaned_data

class QuickQuoteForm(forms.Form):
    """
    A simplified form for creating quick quotes from templates or common scenarios.
    This is perfect for phone calls or walk-in customers where speed is essential.
    """
    
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(status__in=['prospect', 'client']),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-live-search': 'true',
        })
    )
    
    quote_template = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select a template to pre-populate common items"
    )
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'What is this quote for?',
        })
    )
    
    urgent = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Mark as urgent for priority handling"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show active templates
        self.fields['quote_template'].queryset = QuoteTemplate.objects.filter(
            is_active=True
        ).order_by('name')

class BulkQuoteUpdateForm(forms.Form):
    """
    Form for updating multiple quotes at once. Useful for batch operations
    like changing status, assigning to team members, or applying bulk discounts.
    """
    
    action = forms.ChoiceField(
        choices=[
            ('assign', 'Assign to Team Member'),
            ('status', 'Change Status'),
            ('discount', 'Apply Discount'),
            ('extend_validity', 'Extend Validity'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Conditional fields based on action
    assigned_to = forms.ModelChoiceField(
        queryset=None,  # Set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=Quote.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    discount_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100',
            'step': '0.01',
        })
    )
    
    extend_days = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '365',
        }),
        help_text="Number of days to extend validity"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only employees can be assigned quotes
        from core.models import UserProfile
        self.fields['assigned_to'].queryset = User.objects.filter(
            profile__user_type__in=['employee', 'blitzhub_admin']
        ).order_by('first_name', 'last_name')

class QuoteSearchForm(forms.Form):
    """
    Advanced search form for finding quotes. This supports multiple criteria
    to help users quickly find the quotes they're looking for.
    """
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search quote number, client name, or description...',
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + Quote.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    client = forms.ModelChoiceField(
        required=False,
        queryset=Client.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-live-search': 'true',
        })
    )
    
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=None,  # Set in __init__
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
        })
    )
    
    amount_min = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '0.01',
            'placeholder': 'Minimum amount',
        })
    )
    
    amount_max = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'step': '0.01',
            'placeholder': 'Maximum amount',
        })
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('quote_number', 'Quote Number'),
            ('client__name', 'Client Name'),
            ('-total_amount', 'Highest Value'),
            ('total_amount', 'Lowest Value'),
            ('validity_date', 'Expiring Soon'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only show team members who have created quotes
        self.fields['assigned_to'].queryset = User.objects.filter(
            created_quotes__isnull=False
        ).distinct().order_by('first_name', 'last_name')
