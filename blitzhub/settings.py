"""
Django settings for blitzhub project with Enhanced Quote System Integration.
"""

from datetime import timedelta
import os
from pathlib import Path
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()  # Load environment variables before using them

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG')

ALLOWED_HOSTS = ['157.245.102.151', 'localhost', '127.0.0.1', 'blitztechelectronics.co.zw', 'blitztechelectronics.com', 'www.blitztechelectronics.co.zw', 'www.blitztechelectronics.com']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    #Third Party
    'sslserver',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'django.contrib.humanize',

    #Apps
    'core',
    'crm',
    'quotes', 
    'website',
    'inventory',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.EmployeeAccessMiddleware',
]

ROOT_URLCONF = 'blitzhub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'core', 'templates'),
            os.path.join(BASE_DIR, 'quotes', 'templates'),  # NEW: Quote templates
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'core.context_processors.auth_context',
                'core.context_processors.quote_context_processor',      # NEW
                'core.context_processors.system_context_processor',     # NEW  
                'website.context_processors.website_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'blitzhub.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

CSRF_TRUSTED_ORIGINS = [
    "https://127.0.0.1",
    "http://localhost",
    "https://blitztechelectronics.com",
    "https://blitztechelectronics.co.zw",
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Harare'  # Zimbabwe timezone
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'core' / 'static',
    BASE_DIR / 'quotes' / 'static',
    BASE_DIR / 'crm' / 'static',
    BASE_DIR / 'inventory' / 'static',
    BASE_DIR / 'website' / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms settings
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Authentication settings
LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'website:home'

# Email settings (for contact form)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND')
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

# =====================================
# ENHANCED COMPANY INFORMATION FOR EMAILS AND QUOTES
# =====================================
COMPANY_NAME = 'BlitzTech Electronics'
COMPANY_ADDRESS = 'Harare, Zimbabwe'
COMPANY_PHONE = '+263 XX XXX XXXX'
COMPANY_EMAIL = 'info@blitztech.co.zw'
COMPANY_WEBSITE = 'www.blitztech.co.zw'
COMPANY_TAX_NUMBER = 'TAX123456789'  # NEW: For quote system
SUPPORT_EMAIL = 'support@blitztech.co.zw'

# Management notification emails
MANAGEMENT_NOTIFICATION_EMAILS = [
    'manager@blitztech.co.zw',
    'director@blitztech.co.zw',
]

MANAGEMENT_CC_EMAILS = [
    'sales-manager@blitztech.co.zw',
]

# Site URL for generating absolute URLs in emails
SITE_URL = 'https://blitztechelectronics.co.zw'  # Updated to your domain

# =====================================
# ENHANCED QUOTE SYSTEM SETTINGS
# =====================================

# Quote System Defaults
DEFAULT_QUOTE_VALIDITY_DAYS = 30
DEFAULT_PAYMENT_TERMS = 30  # Days
DEFAULT_TAX_RATE = Decimal('15.00')  # Zimbabwe VAT rate
DEFAULT_CURRENCY = 'USD'
SUPPORTED_CURRENCIES = ['USD', 'ZWG']

# Business Rules for Quote Approval
HIGH_VALUE_QUOTE_THRESHOLD = Decimal('10000.00')  # Quotes above this need approval
HIGH_DISCOUNT_THRESHOLD = Decimal('20.00')        # Discounts above this need approval
LOW_MARGIN_THRESHOLD = Decimal('15.00')           # Margins below this need approval

# PDF Generation Settings
PDF_SHOW_PROFIT_ANALYSIS = False  # Don't show internal profit data in client PDFs
PDF_SHOW_TERMS = True
PDF_FOOTER_TEXT = 'Thank you for choosing BlitzTech Electronics'
PDF_COLOR_SCHEME = 'blue'
PDF_WATERMARK = None  # Optional watermark text

# File Upload Settings (for attachments)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Security Settings for Client Portal
SECURE_ACCESS_TOKEN_LENGTH = 32
ACCESS_TOKEN_EXPIRY_DAYS = 90  # How long client access links remain valid
CLIENT_PORTAL_ACCESS_TOKEN_EXPIRY = 30  # Days

# =====================================
# ENHANCED INTEGRATION SETTINGS
# =====================================
# CRM Integration
CRM_AUTO_CREATE_INTERACTIONS = True
CRM_AUTO_UPDATE_CLIENT_VALUE = True

# Inventory Integration  
INVENTORY_AUTO_RESERVE = False  # Reserve stock when quotes are accepted
INVENTORY_CHECK_AVAILABILITY = True

# Notification Settings
ENABLE_EMAIL_NOTIFICATIONS = True
ENABLE_INTERNAL_NOTIFICATIONS = True
QUOTE_NOTIFICATION_THRESHOLD = Decimal('5000.00')  # Notify management for quotes above this amount

AUTH_USER_MODEL = 'auth.User'  # Using Django's default user model

# Authentication and security settings
PASSWORD_EXPIRY_DAYS = 90  # Password expires after 90 days
MAX_LOGIN_ATTEMPTS = 5  # Maximum failed login attempts before temporary lockout
LOGIN_BLOCK_TIME = 1800  # Block time in seconds (30 minutes) after max attempts
REQUIRE_PASSWORD_HISTORY = 5  # Number of old passwords that cannot be reused
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Force login after browser close
SESSION_COOKIE_AGE = 1800  # 30 minutes
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session with each request to keep it active

# =====================================
# ENHANCED ACCESS CONTROL RULES WITH QUOTE INTEGRATION
# =====================================
ACCESS_CONTROL_RULES = {
    # Core application access rules
    'core:dashboard': {
        'login_required': True,
        'user_types': ['employee', 'sales_rep', 'sales_manager', 'blitzhub_admin', 'it_admin'],
        'failure_url': 'website:home',
        'access_denied_message': 'Employee access required for dashboard.',
    },
    'core:employee_list': {
        'login_required': True,
        'user_types': ['blitzhub_admin', 'it_admin'],
        'access_denied_message': 'Administrator access required.',
    },
    'core:add_employee': {
        'login_required': True,
        'user_types': ['blitzhub_admin', 'it_admin'],
        'access_denied_message': 'Administrator access required.',
    },
    
    # Quote system access rules
    'quotes:*': {  # Applies to all quote URLs
        'login_required': True,
        'app_permission': {'app': 'quotes', 'level': 'view'},
        'failure_url': 'core:dashboard',
        'access_denied_message': 'Quote system access required.',
    },
    'quotes:quote_create': {
        'login_required': True,
        'app_permission': {'app': 'quotes', 'level': 'edit'},
        'access_denied_message': 'Quote creation permission required.',
    },
    'quotes:quote_builder': {
        'login_required': True,
        'app_permission': {'app': 'quotes', 'level': 'edit'},
        'access_denied_message': 'Quote editing permission required.',
    },
    'quotes:approve_quote': {
        'login_required': True,
        'user_types': ['sales_manager', 'blitzhub_admin', 'it_admin'],
        'access_denied_message': 'Quote approval authority required.',
    },
    'quotes:quote_analytics': {
        'login_required': True,
        'app_permission': {'app': 'quotes', 'level': 'admin'},
        'access_denied_message': 'Quote analytics access requires admin permissions.',
    },
    
    # CRM integration rules
    'crm:*': {
        'login_required': True,
        'app_permission': {'app': 'crm', 'level': 'view'},
        'failure_url': 'core:dashboard',
    },
    
    # Inventory integration rules
    'inventory:*': {
        'login_required': True,
        'app_permission': {'app': 'inventory', 'level': 'view'},
        'failure_url': 'core:dashboard',
    },
    
    # Shop management
    'shop:manage_*': {
        'login_required': True,
        'access_check': 'core.utils.check_app_permission',
        'access_check_args': {'app_name': 'shop', 'required_level': 'edit'},
        'failure_url': 'website:home',
        'access_denied_message': 'You do not have access to shop management.'
    },
    
    # Website management
    'website:manage_*': {
        'login_required': True,
        'access_check': 'core.utils.check_app_permission',
        'access_check_args': {'app_name': 'website', 'required_level': 'edit'},
        'failure_url': 'website:home',
        'access_denied_message': 'You do not have access to website management.'
    },
    
    # Employee management
    'core:employee_*': {
        'login_required': True,
        'user_types': ['blitzhub_admin', 'it_admin'],
        'failure_url': 'core:dashboard',
        'access_denied_message': 'You do not have permission to manage employees.'
    },
    
    # Permission management (IT admin only)
    'core:manage_permissions': {
        'login_required': True,
        'user_types': ['it_admin'],
        'failure_url': 'core:dashboard',
        'access_denied_message': 'Only IT administrators can manage permissions.'
    }
}

# List of authentication-related views that should be exempt from access controls
AUTH_VIEWS = [
    ('core', 'login'), 
    ('core', 'logout'),
    ('core', 'register'),
    ('shop', 'login'),
    ('website', 'login'),
    # Quote public views (client portal)
    ('quotes', 'quote_preview_public'),
    ('quotes', 'quote_accept_public'),
    ('quotes', 'quote_feedback_public'),
    ('quotes', 'quote_download_public'),
    ('quotes', 'quote_contact_public'),
]

# =====================================
# ENHANCED LOGGING CONFIGURATION WITH QUOTE TRACKING
# =====================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'security': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'crm_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/crm.log',
        },
        'quote_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/quotes.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'blitzhub.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'security_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'security.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 10,
            'formatter': 'security',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'crm': {
            'handlers': ['crm_file'],
            'level': 'INFO',
            'propagate': True,
        },
        'quotes': {
            'handlers': ['quote_file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['console', 'file', 'mail_admins'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['security_file', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'core.security': {
            'handlers': ['security_file', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# CRM Configuration
CRM_SETTINGS = {
    'DEFAULT_FOLLOWUP_DAYS': 7,
    'AUTO_ASSIGN_LEADS': True,
    'LEAD_SCORING_ENABLED': True,
    'EMAIL_NOTIFICATIONS': True,
    'ANALYTICS_RETENTION_DAYS': 365,
}

# =====================================
# FEATURE FLAGS FOR QUOTE SYSTEM
# =====================================
FEATURE_FLAGS = {
    'NEW_QUOTE_BUILDER': True,
    'ADVANCED_ANALYTICS': True,
    'BULK_OPERATIONS': True,
    'CLIENT_PORTAL': True,
    'QUOTE_TEMPLATES': True,
    'MOBILE_ACCESS': True,
    'AI_PRICING_SUGGESTIONS': False,  # Future feature
    'AUTOMATED_FOLLOWUPS': False,     # Future feature
}

# =====================================
# PERFORMANCE MONITORING
# =====================================
SLOW_QUERY_THRESHOLD = 2.0  # Log queries taking more than 2 seconds
SLOW_REQUEST_THRESHOLD = 5.0  # Log requests taking more than 5 seconds

# =====================================
# CACHING CONFIGURATION
# =====================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        # For production, use Redis:
        # 'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        # 'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# Cache settings for performance optimization
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = 'blitztech'
