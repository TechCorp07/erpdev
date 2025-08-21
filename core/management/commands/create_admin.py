# core/management/commands/create_admin.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import UserProfile, EmployeeRole, UserRole

class Command(BaseCommand):
    help = 'Create admin user with full permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='admin',
            help='Admin username (default: admin)',
        )
        parser.add_argument(
            '--email',
            type=str,
            default='admin@blitztechelectronics.co.zw',
            help='Admin email',
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Admin password (default: admin123)',
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        
        self.stdout.write(f'Creating admin user: {username}')
        
        try:
            with transaction.atomic():
                # Create or get user
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': email,
                        'first_name': 'System',
                        'last_name': 'Administrator',
                        'is_staff': True,
                        'is_superuser': True,
                        'is_active': True
                    }
                )
                
                if created:
                    user.set_password(password)
                    user.save()
                    self.stdout.write(f'✓ Created user: {username}')
                else:
                    self.stdout.write(f'✓ User {username} already exists')
                
                # Ensure profile exists
                profile, profile_created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'user_type': 'employee',
                        'department': 'admin',
                        'phone': '+263777123456',
                        'is_approved': True,
                        'profile_completed': True
                    }
                )
                
                if profile_created:
                    self.stdout.write('✓ Created user profile')
                else:
                    # Update existing profile
                    profile.user_type = 'employee'
                    profile.department = 'admin'
                    profile.is_approved = True
                    profile.profile_completed = True
                    profile.save()
                    self.stdout.write('✓ Updated user profile')
                
                # Assign business owner role
                try:
                    business_owner_role = EmployeeRole.objects.get(name='business_owner')
                    user_role, role_created = UserRole.objects.get_or_create(
                        user=user,
                        role=business_owner_role,
                        defaults={'is_active': True}
                    )
                    
                    if role_created:
                        self.stdout.write('✓ Assigned business_owner role')
                    else:
                        user_role.is_active = True
                        user_role.save()
                        self.stdout.write('✓ Activated business_owner role')
                        
                except EmployeeRole.DoesNotExist:
                    self.stdout.write(self.style.WARNING('⚠ business_owner role not found'))
                
                # Clear any cached permissions
                from core.utils import invalidate_permission_cache
                invalidate_permission_cache(user.id)
                
                self.stdout.write(self.style.SUCCESS(f'''
Admin user created successfully!
Username: {username}
Email: {email}
Password: {password}
Type: Business Owner (full access)

You can now login at: /auth/login/?type=employee
                '''))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating admin user: {e}'))
