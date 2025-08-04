# core/management/commands/setup_quote_system.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import UserProfile, AppPermission, SystemSetting
from core.utils import create_notification

class Command(BaseCommand):
    help = 'Set up the quote system for existing installation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force setup even if already configured',
        )
        parser.add_argument(
            '--create-demo-data',
            action='store_true',
            help='Create demo sales representatives and managers',
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up quote system...'))
        
        with transaction.atomic():
            # Set up system settings
            self.setup_system_settings(options['force'])
            
            # Set up default permissions
            self.setup_default_permissions()
            
            # Create demo data if requested
            if options['create_demo_data']:
                self.create_demo_users()
            
            # Verify installation
            self.verify_installation()
        
        self.stdout.write(
            self.style.SUCCESS('Quote system setup completed successfully!')
        )
    
    def setup_system_settings(self, force=False):
        """Set up default system settings"""
        settings_data = [
            ('COMPANY_NAME', 'BlitzTech Electronics', 'company'),
            ('COMPANY_ADDRESS', 'Harare, Zimbabwe', 'company'),
            ('COMPANY_PHONE', '+263 XX XXX XXXX', 'company'),
            ('COMPANY_EMAIL', 'info@blitztech.co.zw', 'company'),
            ('COMPANY_WEBSITE', 'www.blitztech.co.zw', 'company'),
            ('DEFAULT_QUOTE_VALIDITY_DAYS', '30', 'quotes'),
            ('DEFAULT_PAYMENT_TERMS', '30', 'quotes'),
            ('DEFAULT_TAX_RATE', '15.00', 'quotes'),
            ('HIGH_VALUE_QUOTE_THRESHOLD', '10000.00', 'quotes'),
            ('HIGH_DISCOUNT_THRESHOLD', '20.00', 'quotes'),
            ('QUOTE_EMAIL_FROM', 'quotes@blitztech.co.zw', 'email'),
        ]
        
        created_count = 0
        for key, value, category in settings_data:
            setting, created = SystemSetting.objects.get_or_create(
                key=key,
                defaults={
                    'value': value,
                    'category': category,
                    'description': f'Quote system setting: {key}',
                    'is_active': True
                }
            )
            
            if created or force:
                if force and not created:
                    setting.value = value
                    setting.save()
                created_count += 1
        
        self.stdout.write(f'  - Set up {created_count} system settings')
    
    def setup_default_permissions(self):
        """Set up default permissions for existing users"""
        permission_mappings = {
            'employee': {'quotes': 'view', 'financial': 'view', 'reports': 'view'},
            'sales_rep': {'quotes': 'edit', 'financial': 'view', 'reports': 'view'},
            'sales_manager': {'quotes': 'admin', 'financial': 'edit', 'reports': 'admin'},
            'blitzhub_admin': {'quotes': 'admin', 'financial': 'admin', 'reports': 'admin'},
            'it_admin': {'quotes': 'admin', 'financial': 'view', 'reports': 'admin'},
        }
        
        updated_count = 0
        for profile in UserProfile.objects.all():
            user_type = profile.user_type
            if user_type in permission_mappings:
                permissions = permission_mappings[user_type]
                
                for app, level in permissions.items():
                    permission, created = AppPermission.objects.get_or_create(
                        user=profile.user,
                        app=app,
                        defaults={'permission_level': level}
                    )
                    if created:
                        updated_count += 1
        
        self.stdout.write(f'  - Set up {updated_count} user permissions')
    
    def create_demo_users(self):
        """Create demo sales representatives and managers"""
        demo_users = [
            {
                'username': 'sales_rep_demo',
                'email': 'salesrep@blitztech.co.zw',
                'first_name': 'John',
                'last_name': 'Sales',
                'user_type': 'sales_rep',
                'department': 'sales'
            },
            {
                'username': 'sales_manager_demo',
                'email': 'salesmanager@blitztech.co.zw',
                'first_name': 'Jane',
                'last_name': 'Manager',
                'user_type': 'sales_manager',
                'department': 'sales'
            }
        ]
        
        created_count = 0
        for user_data in demo_users:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={
                    'email': user_data['email'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'is_active': True
                }
            )
            
            if created:
                user.set_password('demo123456')
                user.save()
                
                # Update profile
                profile = user.profile
                profile.user_type = user_data['user_type']
                profile.department = user_data['department']
                profile.requires_password_change = True
                profile.save()
                
                # Set up permissions using your utility function
                from core.utils import setup_default_user_permissions
                setup_default_user_permissions(user)
                
                # Send welcome notification
                create_notification(
                    user=user,
                    title="Welcome to BlitzTech Quote System",
                    message="Your demo account has been created. Please change your password on first login.",
                    notification_type="info"
                )
                
                created_count += 1
        
        if created_count > 0:
            self.stdout.write(f'  - Created {created_count} demo users')
            self.stdout.write('    Demo credentials: username/demo123456')
    
    def verify_installation(self):
        """Verify the quote system is properly installed"""
        issues = []
        
        # Check if quote app is installed
        try:
            from quotes.models import Quote
        except ImportError:
            issues.append("Quote app not installed or not in INSTALLED_APPS")
        
        # Check system settings
        required_settings = ['COMPANY_NAME', 'DEFAULT_TAX_RATE', 'HIGH_VALUE_QUOTE_THRESHOLD']
        missing_settings = []
        for setting_key in required_settings:
            if not SystemSetting.objects.filter(key=setting_key, is_active=True).exists():
                missing_settings.append(setting_key)
        
        if missing_settings:
            issues.append(f"Missing system settings: {', '.join(missing_settings)}")
        
        # Check if sales team exists
        sales_team_count = UserProfile.objects.filter(
            user_type__in=['sales_rep', 'sales_manager']
        ).count()
        
        if sales_team_count == 0:
            issues.append("No sales team members found. Use --create-demo-data to create demo users.")
        
        if issues:
            self.stdout.write(
                self.style.WARNING('Installation issues found:')
            )
            for issue in issues:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(
                self.style.SUCCESS('Quote system installation verified successfully!')
            )
