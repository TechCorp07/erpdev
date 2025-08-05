# core/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
import logging

logger = logging.getLogger('core.authentication')


class CustomAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for regular registration"""
    
    def is_open_for_signup(self, request):
        """Control who can sign up"""
        # Allow signup for customers and bloggers only
        # Employees are created by admin
        return True
    
    def save_user(self, request, user, form, commit=True):
        """Enhanced user saving with profile setup"""
        user = super().save_user(request, user, form, commit=False)
        
        # Get user type from form or default to customer
        user_type = getattr(form, 'cleaned_data', {}).get('user_type', 'customer')
        
        if commit:
            user.save()
            
            # Ensure profile exists and set up approval workflow
            profile = user.profile
            profile.user_type = user_type
            profile.social_provider = 'manual'
            
            # Set initial approval status based on user type
            if user_type == 'customer':
                profile.shop_approved = True  # Customers can shop immediately
                profile.crm_approved = False  # But need approval for CRM
            elif user_type == 'blogger':
                profile.shop_approved = True  # Bloggers can shop
                profile.crm_approved = False  # Need approval for CRM
                profile.blog_approved = False  # Need approval for blog management
            
            profile.save()
            
            # Create approval request for non-shop access
            self._create_approval_requests(user, user_type)
            
            # Log registration
            logger.info(f"New user registered: {user.username} ({user_type})")
            
        return user
    
    def _create_approval_requests(self, user, user_type):
        """Create initial approval requests"""
        from .models import ApprovalRequest
        
        requests_to_create = []
        
        if user_type in ['customer', 'blogger']:
            # Request CRM access
            requests_to_create.append(('crm', 'Access to customer relationship management system'))
        
        if user_type == 'blogger':
            # Request blog management access
            requests_to_create.append(('blog', 'Access to blog content management'))
        
        for request_type, reason in requests_to_create:
            ApprovalRequest.objects.get_or_create(
                user=user,
                request_type=request_type,
                status='pending',
                defaults={
                    'requested_reason': reason,
                    'business_justification': f'New {user_type} registration requiring {request_type} access'
                }
            )
    
    def get_login_redirect_url(self, request):
        """Redirect after login based on profile completion"""
        user = request.user
        
        if hasattr(user, 'profile'):
            if not user.profile.profile_completed:
                return reverse('core:profile_completion')
            elif user.profile.user_type == 'employee':
                return reverse('core:dashboard')
            else:
                return reverse('core:customer_dashboard')
        
        return super().get_login_redirect_url(request)


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Facebook/Google login"""
    
    def is_open_for_signup(self, request, sociallogin):
        """Allow social signup for customers and bloggers"""
        return True
    
    def pre_social_login(self, request, sociallogin):
        """Handle social login preprocessing"""
        # Check if user already exists with this email
        if sociallogin.user.email:
            try:
                from django.contrib.auth.models import User
                existing_user = User.objects.get(email=sociallogin.user.email)
                
                if not sociallogin.is_existing:
                    # Connect existing account with social account
                    sociallogin.connect(request, existing_user)
                    
                    # Update profile to mark as social
                    if hasattr(existing_user, 'profile'):
                        existing_user.profile.is_social_account = True
                        existing_user.profile.social_verified = True
                        existing_user.profile.save()
                        
                    messages.info(request, 'Your existing account has been connected to your social login.')
                    
            except User.DoesNotExist:
                pass  # New user, will be handled in save_user
    
    def save_user(self, request, sociallogin, form=None):
        """Enhanced social user saving"""
        user = super().save_user(request, sociallogin, form)
        
        # Extract additional info from social account
        extra_data = sociallogin.account.extra_data
        provider = sociallogin.account.provider
        
        # Set up profile for social users
        profile = user.profile
        profile.is_social_account = True
        profile.social_provider = provider
        profile.social_verified = True
        profile.user_type = 'customer'  # Default for social signups
        
        # Extract profile picture if available
        if provider == 'google' and 'picture' in extra_data:
            profile.profile_image_url = extra_data['picture']
        elif provider == 'facebook' and extra_data.get('id'):
            profile.profile_image_url = f"https://graph.facebook.com/{extra_data['id']}/picture?type=large"
        
        # Set approval status
        profile.shop_approved = True  # Can shop immediately
        profile.crm_approved = False  # Needs approval for CRM
        profile.save()
        
        # Create approval request for CRM access
        self._create_social_approval_request(user, provider)
        
        # Log social registration
        logger.info(f"New social user registered: {user.username} via {provider}")
        
        return user
    
    def _create_social_approval_request(self, user, provider):
        """Create approval request for social users"""
        from .models import ApprovalRequest
        
        ApprovalRequest.objects.get_or_create(
            user=user,
            request_type='crm',
            status='pending',
            defaults={
                'requested_reason': f'New user registered via {provider} requesting CRM access',
                'business_justification': f'Social registration through {provider} - customer account'
            }
        )
    
    def get_connect_redirect_url(self, request, socialaccount):
        """Redirect after connecting social account"""
        return reverse('core:profile_completion')
    
    def authentication_error(self, request, provider_id, error=None, exception=None, extra_context=None):
        """Handle authentication errors"""
        messages.error(request, f'Social authentication with {provider_id} failed. Please try again or register manually.')
        logger.warning(f"Social auth error for {provider_id}: {error}")
        
        return redirect('core:register')
    
    def populate_user(self, request, sociallogin, data):
        """Populate user data from social login"""
        user = super().populate_user(request, sociallogin, data)
        
        # Ensure we have required fields
        if not user.first_name and 'first_name' in data:
            user.first_name = data['first_name']
        if not user.last_name and 'last_name' in data:
            user.last_name = data['last_name']
            
        return user
    
    def is_auto_signup_allowed(self, request, sociallogin):
        """Allow automatic signup for social accounts"""
        # Check if email domain is allowed (optional business rule)
        email = sociallogin.user.email
        
        # Add any business rules here
        # For example, block certain domains:
        blocked_domains = getattr(settings, 'BLOCKED_EMAIL_DOMAINS', [])
        if email and any(email.endswith(domain) for domain in blocked_domains):
            return False
            
        return True
    
    def get_signup_redirect_url(self, request):
        """Redirect after social signup"""
        return reverse('core:profile_completion')


class CustomPasswordValidator:
    """Custom password validator for commercial grade security"""
    
    def validate(self, password, user=None):
        """Validate password meets business requirements"""
        errors = []
        
        # Check for uppercase letters
        if not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter.")
        
        # Check for lowercase letters
        if not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter.")
        
        # Check for digits
        if not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit.")
        
        # Check for special characters
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character.")
        
        # Check against common patterns
        common_patterns = ['123', 'abc', 'password', 'admin', 'user']
        password_lower = password.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                errors.append(f"Password cannot contain common pattern: {pattern}")
        
        if errors:
            from django.core.exceptions import ValidationError
            raise ValidationError(errors)
    
    def get_help_text(self):
        return (
            "Your password must contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character."
        )