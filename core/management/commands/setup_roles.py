
# core/management/commands/setup_roles.py
"""
Management command to setup the clean role-based authentication system
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import EmployeeRole, UserRole, AppPermission, UserProfile, initialize_default_roles
from core.utils import setup_default_permissions, assign_role_to_user
import logging

logger = logging.getLogger('core.setup')

class Command(BaseCommand):
    help = 'Setup clean role-based authentication system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean existing roles and permissions before setup',
        )
        parser.add_argument(
            '--migrate-users',
            action='store_true',
            help='Migrate existing users to new role system',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Setting up clean role-based authentication system...')
        )

        with transaction.atomic():
            if options['clean']:
                self.clean_existing_system()

            self.setup_roles()
            self.setup_permissions()

            if options['migrate_users']:
                self.migrate_existing_users()

        self.stdout.write(
            self.style.SUCCESS('Role-based authentication system setup complete!')
        )

    def clean_existing_system(self):
        """Clean existing roles and permissions"""
        self.stdout.write("Cleaning existing system...")
        
        UserRole.objects.all().delete()
        AppPermission.objects.all().delete()
        EmployeeRole.objects.all().delete()
        
        self.stdout.write(self.style.WARNING("Cleaned existing roles and permissions"))

    def setup_roles(self):
        """Setup the 6 default employee roles"""
        self.stdout.write("Setting up employee roles...")
        
        initialize_default_roles()
        
        role_count = EmployeeRole.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Created {role_count} employee roles")
        )

    def setup_permissions(self):
        """Setup default permissions for roles"""
        self.stdout.write("Setting up role permissions...")
        
        setup_default_permissions()
        
        permission_count = AppPermission.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f"Created {permission_count} permissions")
        )

    def migrate_existing_users(self):
        """Migrate existing users to new role system"""
        self.stdout.write("Migrating existing users...")
        
        # Migration mapping from old user_type to new roles
        migration_mapping = {
            'blitzhub_admin': ['business_owner'],
            'it_admin': ['system_admin', 'procurement_officer', 'accounting'],
            'sales_rep': ['sales_manager'],  # Promote for now
            'sales_manager': ['sales_manager'],
            'employee': ['service_tech'],  # Default assignment
        }
        
        migrated_count = 0
        
        for user in User.objects.filter(profile__user_type='employee'):
            profile = user.profile
            old_user_type = getattr(profile, 'original_user_type', None)
            
            if old_user_type in migration_mapping:
                roles_to_assign = migration_mapping[old_user_type]
                
                for role_name in roles_to_assign:
                    try:
                        assign_role_to_user(user, role_name)
                        migrated_count += 1
                        self.stdout.write(f"  Assigned {role_name} to {user.username}")
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  Failed to assign {role_name} to {user.username}: {e}")
                        )
        
        self.stdout.write(
            self.style.SUCCESS(f"Migrated {migrated_count} role assignments")
        )
