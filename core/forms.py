from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from .models import UserProfile, AppPermission

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
    first_name = forms.CharField(
        max_length=30, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=30, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        max_length=254, required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = UserProfile
        fields = ('phone', 'address', 'profile_image')
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'profile_image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        # Always pop 'user' if present
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

            if commit:
                self.user.save()
                profile.save()

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
