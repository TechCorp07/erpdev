from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import UserProfile, AppPermission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from allauth.account.forms import SignupForm
from .models import UserProfile, ApprovalRequest
import re


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


class ProfileCompletionForm(forms.ModelForm):
    """Form for completing user profile after registration/social login"""
    
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
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email Address'
        })
    )
    
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'address', 'company_name', 'tax_number', 
            'billing_address', 'shipping_address', 'same_as_billing'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+263 XX XXX XXXX'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Your physical address'
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company Name (if applicable)'
            }),
            'tax_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Tax Number (if applicable)'
            }),
            'billing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Billing address for invoices'
            }),
            'shipping_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Shipping address for deliveries'
            }),
            'same_as_billing': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Pre-populate with user data if available
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email
        
        # Make fields required based on user type
        if self.instance and self.instance.user_type in ['customer', 'blogger']:
            self.fields['phone'].required = True
            self.fields['address'].required = True
            self.fields['billing_address'].required = True
    
    def clean_phone(self):
        """Validate phone number"""
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_pattern = r'^\+263[0-9]{9}$|^0[0-9]{9}$'
            if not re.match(phone_pattern, phone.replace(' ', '')):
                raise ValidationError("Please enter a valid Zimbabwe phone number")
        return phone
    
    def save(self, commit=True):
        """Save profile and update user fields"""
        profile = super().save(commit=False)
        
        if self.user:
            # Update user fields
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        
        if commit:
            profile.save()
            
            # Check if profile is now complete
            profile.check_profile_completion()
            
            # If profile is complete, create welcome notification
            if profile.profile_completed:
                from .utils import create_notification
                create_notification(
                    user=profile.user,
                    title="Profile Completed!",
                    message="Your profile is now complete. You can access all approved features.",
                    notification_type='success'
                )
        
        return profile


class ApprovalRequestForm(forms.ModelForm):
    """Form for requesting additional access"""
    
    class Meta:
        model = ApprovalRequest
        fields = ['request_type', 'requested_reason', 'business_justification']
        widgets = {
            'request_type': forms.Select(attrs={'class': 'form-control'}),
            'requested_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Please explain why you need this access...'
            }),
            'business_justification': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide business justification for this request...'
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter request types based on user type and current approvals
        if self.user and hasattr(self.user, 'profile'):
            profile = self.user.profile
            available_choices = []
            
            if not profile.crm_approved:
                available_choices.append(('crm', 'CRM Access'))
            
            if profile.user_type == 'blogger' and not profile.blog_approved:
                available_choices.append(('blog', 'Blog Management'))
            
            self.fields['request_type'].choices = available_choices
    
    def clean(self):
        """Validate that user doesn't have pending request of same type"""
        cleaned_data = super().clean()
        request_type = cleaned_data.get('request_type')
        
        if self.user and request_type:
            existing_request = ApprovalRequest.objects.filter(
                user=self.user,
                request_type=request_type,
                status='pending'
            ).exists()
            
            if existing_request:
                raise ValidationError(f"You already have a pending request for {request_type} access.")
        
        return cleaned_data


class AdminApprovalForm(forms.ModelForm):
    """Form for admin to approve/reject requests"""
    
    ACTION_CHOICES = [
        ('approve', 'Approve Request'),
        ('reject', 'Reject Request'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = ApprovalRequest
        fields = ['review_notes']
        widgets = {
            'review_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add notes about this decision...'
            })
        }
    
    def save(self, reviewer, commit=True):
        """Process the approval/rejection"""
        approval_request = super().save(commit=False)
        action = self.cleaned_data['action']
        notes = self.cleaned_data['review_notes']
        
        if commit:
            if action == 'approve':
                approval_request.approve(reviewer, notes)
            else:
                approval_request.reject(reviewer, notes)
        
        return approval_request


class CoreLoginForm(AuthenticationForm):
    """Custom login form with Bootstrap styling"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Username',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Password'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class UserRegistrationForm(UserCreationForm):
    """User registration form with extended profile fields"""
    
    first_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    
    last_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    
    email = forms.EmailField(
        max_length=254, 
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    
    phone = forms.CharField(
        max_length=20, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'})
    )
    
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'placeholder': 'Address',
            'rows': 3
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        # Update widget attributes for built-in fields
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})
    
    def save(self, commit=True):
        user = super(UserRegistrationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            # Update profile fields
            profile = user.profile
            profile.phone = self.cleaned_data.get('phone')
            profile.address = self.cleaned_data.get('address')
            profile.save()
            
        return user


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    first_name = forms.CharField(max_length=30, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(max_length=30, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(max_length=254, required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserProfile
        fields = [
            'phone', 'address', 'profile_image', 'company_name', 'tax_number', 'business_registration',
            'billing_address', 'shipping_address', 'same_as_billing',
            'email_notifications', 'sms_notifications', 'marketing_emails',
            'theme_preference'
        ]
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_number': forms.TextInput(attrs={'class': 'form-control'}),
            'business_registration': forms.TextInput(attrs={'class': 'form-control'}),
            'billing_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'same_as_billing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'marketing_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'theme_preference': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        if not self.user and 'instance' in kwargs and kwargs['instance']:
            self.user = kwargs['instance'].user
        super(UserProfileForm, self).__init__(*args, **kwargs)

        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super(UserProfileForm, self).save(commit=False)

        # Update user model fields
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()

            if commit:
                profile.save()
                profile.check_profile_completion()

        return profile


class PasswordChangeCustomForm(PasswordChangeForm):
    """Custom password change form with bootstrap styling"""
    
    def __init__(self, *args, **kwargs):
        super(PasswordChangeCustomForm, self).__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Current Password'})
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'New Password'})
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm New Password'})


class EmployeeRegistrationForm(UserRegistrationForm):
    """Form for admin to register employees"""
    
    user_type = forms.ChoiceField(
        choices=UserProfile.USER_TYPES[1:],  # Skip 'customer' option
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    department = forms.ChoiceField(
        choices=UserProfile.DEPARTMENTS,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def save(self, commit=True):
        user = super(EmployeeRegistrationForm, self).save(commit=False)
        
        if commit:
            user.save()
            # Update profile with employee fields
            profile = user.profile
            profile.user_type = self.cleaned_data.get('user_type')
            profile.department = self.cleaned_data.get('department')
            profile.save()
            
        return user


class AppPermissionForm(forms.ModelForm):
    """Form for managing user application permissions"""
    
    class Meta:
        model = AppPermission
        fields = ('app', 'permission_level')
        widgets = {
            'app': forms.Select(attrs={'class': 'form-control'}),
            'permission_level': forms.Select(attrs={'class': 'form-control'}),
        }
