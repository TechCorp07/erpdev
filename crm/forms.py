from django import forms
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Client, CustomerInteraction, Deal, Task, ClientNote

class ClientForm(forms.ModelForm):
    """Enhanced client form with all business fields"""
    
    class Meta:
        model = Client
        exclude = (
            'client_id', 'total_orders', 'total_value', 'average_order_value', 
            'lifetime_value', 'lead_score', 'conversion_probability',
            'last_contacted', 'last_order_date', 'created_by', 'created_at', 'updated_at'
        )
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name or business name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+263 XX XXX XXXX'}),
            
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company name'}),
            'website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://company.com'}),
            'industry': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Technology, Manufacturing'}),
            'company_size': forms.Select(attrs={'class': 'form-control'}),
            
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Street address'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apartment, suite, etc.'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Province/State'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Postal code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'value': 'Zimbabwe'}),
            
            'status': forms.Select(attrs={'class': 'form-control'}),
            'customer_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            
            'credit_limit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'payment_terms': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '365'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VAT/Tax number'}),
            'currency_preference': forms.Select(attrs={'class': 'form-control'}),
            
            'profit_margin': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            
            'followup_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Public notes visible to client...'}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Internal notes (not visible to client)...'}),
            'tags': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'tag1, tag2, tag3'}),
            
            'source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Website, referral, cold call, etc.'}),
            'referral_source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Who referred them?'}),
            'marketing_campaign': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Campaign name'}),
            
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'account_manager': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add company size choices
        self.fields['company_size'].choices = [
            ('', 'Select company size'),
            ('1-10', '1-10 employees'),
            ('11-50', '11-50 employees'),
            ('51-200', '51-200 employees'),
            ('200+', '200+ employees'),
        ]
        
        # Limit assigned_to and account_manager to employees only
        employee_users = User.objects.filter(
            profile__user_type__in=['employee', 'blitzhub_admin', 'it_admin']
        ).order_by('first_name', 'last_name')
        
        self.fields['assigned_to'].queryset = employee_users
        self.fields['account_manager'].queryset = employee_users
        
        # Add empty choice for assignment fields
        self.fields['assigned_to'].empty_label = "Not assigned"
        self.fields['account_manager'].empty_label = "Not assigned"
        
        # Add help text
        self.fields['tags'].help_text = "Separate tags with commas (e.g., vip, tech-savvy, price-sensitive)"
        self.fields['credit_limit'].help_text = "Maximum credit allowed in USD"
        self.fields['payment_terms'].help_text = "Payment terms in days (e.g., 30 for Net 30)"
        self.fields['profit_margin'].help_text = "Expected profit margin percentage for this client"


class CustomerInteractionForm(forms.ModelForm):
    """Form for recording customer interactions"""
    
    class Meta:
        model = CustomerInteraction
        exclude = ('client', 'created_by', 'created_at', 'updated_at')
        
        widgets = {
            'interaction_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Interaction subject/title'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Detailed notes about the interaction...'}),
            'outcome': forms.Select(attrs={'class': 'form-control'}),
            
            'next_followup': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'followup_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notes for the follow-up...'}),
            
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '600'}),
            'participants': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Other participants in the interaction'}),
            'attachments': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make outcome optional for some interaction types
        self.fields['outcome'].required = False
        self.fields['subject'].required = False
        self.fields['duration_minutes'].required = False
        self.fields['participants'].required = False
        
        # Add help text
        self.fields['next_followup'].help_text = "Schedule the next follow-up"
        self.fields['duration_minutes'].help_text = "Duration in minutes (optional)"
        self.fields['attachments'].help_text = "Upload relevant files (optional)"


class DealForm(forms.ModelForm):
    """Form for managing sales deals"""
    
    class Meta:
        model = Deal
        exclude = ('deal_id', 'actual_close_date', 'created_by', 'created_at', 'updated_at')
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Deal title/name'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Deal description...'}),
            
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            
            'stage': forms.Select(attrs={'class': 'form-control'}),
            'probability': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            
            'expected_close_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            
            'source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lead source'}),
            'competitor': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Competing companies'}),
            'loss_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for loss (if applicable)'}),
        }
    
    def __init__(self, *args, **kwargs):
        client = kwargs.pop('client', None)
        super().__init__(*args, **kwargs)
        
        # Set default currency choices
        self.fields['currency'].choices = [
            ('USD', 'US Dollar'),
            ('ZWG', 'Zimbabwe Gold'),
        ]
        
        # Limit assigned_to to employees
        employee_users = User.objects.filter(
            profile__user_type__in=['employee', 'blitzhub_admin', 'it_admin']
        ).order_by('first_name', 'last_name')
        
        self.fields['assigned_to'].queryset = employee_users
        self.fields['assigned_to'].empty_label = "Not assigned"
        
        # If client is provided, set it and hide the field
        if client:
            self.fields['client'].initial = client
            self.fields['client'].widget = forms.HiddenInput()
        
        # Add help text
        self.fields['probability'].help_text = "Win probability percentage (0-100)"
        self.fields['value'].help_text = "Expected deal value"
        self.fields['loss_reason'].help_text = "Only fill if deal is closed-lost"


class TaskForm(forms.ModelForm):
    """Form for creating and managing tasks"""
    
    class Meta:
        model = Task
        exclude = ('completed_at', 'created_by', 'created_at', 'updated_at')
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Task description...'}),
            
            'client': forms.Select(attrs={'class': 'form-control'}),
            'deal': forms.Select(attrs={'class': 'form-control'}),
            
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        client = kwargs.pop('client', None)
        deal = kwargs.pop('deal', None)
        current_user = kwargs.pop('current_user', None)
        
        super().__init__(*args, **kwargs)
        
        # Limit assigned_to to employees
        employee_users = User.objects.filter(
            profile__user_type__in=['employee', 'blitzhub_admin', 'it_admin']
        ).order_by('first_name', 'last_name')
        
        self.fields['assigned_to'].queryset = employee_users
        
        # Set default assignee to current user
        if current_user and current_user.profile.is_employee:
            self.fields['assigned_to'].initial = current_user
        
        # Make client and deal optional
        self.fields['client'].required = False
        self.fields['deal'].required = False
        self.fields['client'].empty_label = "Not related to specific client"
        self.fields['deal'].empty_label = "Not related to specific deal"
        
        # If client or deal is provided, set it
        if client:
            self.fields['client'].initial = client
        if deal:
            self.fields['deal'].initial = deal
            # If deal is set, filter clients to only the deal's client
            self.fields['client'].initial = deal.client
            self.fields['client'].widget = forms.HiddenInput()


class ClientNoteForm(forms.ModelForm):
    """Form for adding notes to clients"""
    
    class Meta:
        model = ClientNote
        exclude = ('client', 'created_by', 'created_at', 'updated_at')
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Note title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Note content...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['attachment'].required = False
        self.fields['is_private'].help_text = "Check if this note should only be visible to assigned team members"


class ClientSearchForm(forms.Form):
    """Form for searching and filtering clients"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, email, company, or phone...',
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + Client.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    customer_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + Client.CUSTOMER_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    region = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by country/region...',
        })
    )
    
    assigned_to = forms.ModelChoiceField(
        required=False,
        queryset=User.objects.filter(
            profile__user_type__in=['employee', 'blitzhub_admin', 'it_admin']
        ).order_by('first_name', 'last_name'),
        empty_label="All Assigned Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sort = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('name', 'Name A-Z'),
            ('-name', 'Name Z-A'),
            ('-last_contacted', 'Recently Contacted'),
            ('last_contacted', 'Least Recently Contacted'),
            ('-total_value', 'Highest Value'),
            ('total_value', 'Lowest Value'),
        ],
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class InteractionSearchForm(forms.Form):
    """Form for searching interactions"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search notes or client name...',
        })
    )
    
    interaction_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + CustomerInteraction.INTERACTION_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    outcome = forms.ChoiceField(
        required=False,
        choices=[('', 'All Outcomes')] + CustomerInteraction.OUTCOME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )


class QuickInteractionForm(forms.Form):
    """Quick form for adding simple interactions"""
    
    interaction_type = forms.ChoiceField(
        choices=CustomerInteraction.INTERACTION_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Quick notes about this interaction...'
        })
    )
    
    outcome = forms.ChoiceField(
        required=False,
        choices=[('', 'Select outcome')] + CustomerInteraction.OUTCOME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    schedule_followup = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    followup_date = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        schedule_followup = cleaned_data.get('schedule_followup')
        followup_date = cleaned_data.get('followup_date')
        
        if schedule_followup and not followup_date:
            raise forms.ValidationError("Follow-up date is required when scheduling a follow-up.")
        
        return cleaned_data
