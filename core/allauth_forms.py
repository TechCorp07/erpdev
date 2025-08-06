from django import forms
from django.contrib.auth.models import User
from allauth.account.forms import SignupForm
from .models import UserProfile
import re
from django.core.exceptions import ValidationError

class CustomSignupForm(SignupForm):
    """Enhanced signup form with user type selection"""
    
    USER_TYPE_CHOICES = [
        ('customer', 'Customer - I want to browse and purchase products'),
        ('blogger', 'Blogger - I want to write content and manage blogs'),
    ]
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First Name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last Name'
        })
    )
    
    user_type = forms.ChoiceField(
        choices=USER_TYPE_CHOICES,
        required=True,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        help_text="Select your primary use of our platform"
    )
    
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+263 XX XXX XXXX'
        }),
        help_text="Phone number for account verification and support"
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I accept the Terms of Service and Privacy Policy"
    )
    
    marketing_consent = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="I would like to receive marketing emails about new products and services"
    )
    
    def clean_email(self):
        """Validate email uniqueness and format"""
        email = self.cleaned_data.get('email')
        
        if email:
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                raise ValidationError("A user with this email already exists.")
            
            # Business email validation (optional)
            blocked_domains = ['tempmail.com', 'guerrillamail.com']  # Add more as needed
            domain = email.split('@')[1].lower()
            if domain in blocked_domains:
                raise ValidationError("Please use a valid business or personal email address.")
        
        return email
    
    def clean_phone(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone')
        
        if phone:
            # Basic Zimbabwe phone number validation
            phone_pattern = r'^\+263[0-9]{9}$|^0[0-9]{9}$'
            if not re.match(phone_pattern, phone.replace(' ', '')):
                raise ValidationError("Please enter a valid Zimbabwe phone number (e.g., +263XX XXX XXXX)")
        
        return phone
    
    def save(self, request):
        """Enhanced user saving with profile setup"""
        user = super().save(request)
        
        # Update user fields
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        
        # Update profile
        profile = user.profile
        profile.user_type = self.cleaned_data['user_type']
        profile.phone = self.cleaned_data.get('phone', '')
        profile.marketing_emails = self.cleaned_data.get('marketing_consent', False)
        profile.social_provider = 'manual'
        
        # Set approval status based on user type
        if profile.user_type == 'customer':
            profile.shop_approved = True
            profile.crm_approved = False
        elif profile.user_type == 'blogger':
            profile.shop_approved = True
            profile.crm_approved = False
            profile.blog_approved = False
        
        profile.save()
        
        return user

