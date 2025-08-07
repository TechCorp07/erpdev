# core/validators.py
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import CommonPasswordValidator
import re

class CustomPasswordValidator:
    """
    Commercial-grade password validator for BlitzTech Electronics
    """
    
    def validate(self, password, user=None):
        errors = []
        
        # Minimum length check (handled by Django's MinimumLengthValidator)
        
        # Character composition requirements
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one digit.')
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            errors.append('Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?).')
        
        # Check for common patterns
        common_patterns = [
            r'123',          # Sequential numbers
            r'abc',          # Sequential letters
            r'password',     # Common word
            r'admin',        # Common word
            r'user',         # Common word
            r'login',        # Common word
            r'blitztech',    # Company name
            r'electronics',  # Company domain
        ]
        
        password_lower = password.lower()
        for pattern in common_patterns:
            if pattern in password_lower:
                errors.append(f'Password cannot contain "{pattern}".')
        
        # Check for keyboard patterns
        keyboard_patterns = [
            'qwerty', 'asdf', 'zxcv', '1234', 'abcd'
        ]
        
        for pattern in keyboard_patterns:
            if pattern in password_lower:
                errors.append('Password cannot contain common keyboard patterns.')
                break
        
        # Check against user information
        if user:
            user_info = [
                user.username.lower() if user.username else '',
                user.first_name.lower() if user.first_name else '',
                user.last_name.lower() if user.last_name else '',
                user.email.split('@')[0].lower() if user.email else '',
            ]
            
            for info in user_info:
                if info and len(info) >= 3 and info in password_lower:
                    errors.append('Password cannot be based on your personal information.')
                    break
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return (
            "Your password must contain at least one uppercase letter, "
            "one lowercase letter, one digit, and one special character. "
            "It cannot contain common words or patterns."
        )


class EmailDomainValidator:
    """
    Validate email domains for business use
    """
    # Add blocked domains as needed
    BLOCKED_DOMAINS = [
        'tempmail.com',
        'guerrillamail.com',
        '10minutemail.com',
        'mailinator.com',
        'throwaway.email',
    ]
    
    # Add required domains for employees (optional)
    EMPLOYEE_REQUIRED_DOMAINS = [
        'blitztechelectronics.co.zw',
        'blitztechelectronics.co.zw',
    ]
    
    def __init__(self, user_type=None):
        self.user_type = user_type
    
    def __call__(self, email):
        domain = email.split('@')[1].lower()
        
        # Check blocked domains
        if domain in self.BLOCKED_DOMAINS:
            raise ValidationError(
                f'Email addresses from {domain} are not allowed. '
                'Please use a business or personal email address.'
            )
        
        # Check employee domain requirements
        if (self.user_type == 'employee' and 
            self.EMPLOYEE_REQUIRED_DOMAINS and 
            domain not in self.EMPLOYEE_REQUIRED_DOMAINS):
            
            allowed = ', '.join(self.EMPLOYEE_REQUIRED_DOMAINS)
            raise ValidationError(
                f'Employee email addresses must be from: {allowed}'
            )


class PhoneNumberValidator:
    """
    Validate Zimbabwe phone numbers
    """
    
    def __call__(self, phone):
        # Remove spaces and dashes
        clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Zimbabwe phone number patterns
        patterns = [
            r'^\+263[0-9]{9}$',     # International format
            r'^0[0-9]{9}$',         # Local format
            r'^263[0-9]{9}$',       # Without + sign
        ]
        
        valid = any(re.match(pattern, clean_phone) for pattern in patterns)
        
        if not valid:
            raise ValidationError(
                'Please enter a valid Zimbabwe phone number. '
                'Examples: +263771234567, 0771234567'
            )


class BusinessRegistrationValidator:
    """
    Validate Zimbabwe business registration numbers
    """
    
    def __call__(self, registration_number):
        # Basic format validation for Zimbabwe business registration
        # Adjust pattern based on actual Zimbabwe business registration format
        pattern = r'^[A-Z0-9]{5,15}$'
        
        if not re.match(pattern, registration_number.upper()):
            raise ValidationError(
                'Please enter a valid business registration number.'
            )
