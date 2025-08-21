# core/management/commands/migrate_to_roles.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import EmployeeRole, UserRole, AppPermission, UserProfile

class Command(BaseCommand):
    help = 'Migrate from legacy permission system to role-based system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('Starting migration to role-based permission system...')
        
        # Create default roles if they don't exist
        self.create_default_roles(dry_run)
        
        # Migrate users to roles based on their profiles
        self.migrate_users_to_roles(dry_run)
        
        # Set up default permissions for roles
        self.setup_role_permissions(dry_run)
        
        self.stdout.write(self.style.SUCCESS('Migration completed!'))

    def create_default_roles(self, dry_run):
        """Create default employee roles"""
        roles_data = [
            {
                'name': 'business_owner',
                'display_name': 'Business Owner',
                'description': 'Full system access',
                'hierarchy_level': 'executive',
                'can_assign_roles': True,
                'requires_gm_approval': False
            },
            {
                'name': 'system_admin',
                'display_name': 'System Administrator',
                'description': 'Technical system administration',
                'hierarchy_level': 'manager',
                'can_assign_roles': True,
                'requires_gm_approval': False
            },
            {
                'name': 'sales_manager',
                'display_name': 'Sales Manager',
                'description': 'Sales team management',
                'hierarchy_level': 'manager',
                'can_assign_roles': False,
                'requires_gm_approval': False
            },
            {
                'name': 'sales_rep',
                'display_name': 'Sales Representative',
                'description': 'Customer interaction and sales',
                'hierarchy_level': 'staff',
                'can_assign_roles': False,
                'requires_gm_approval': True
            },
            {
                'name': 'procurement_officer',
                'display_name': 'Procurement Officer',
                'description': 'Inventory and supplier management',
                'hierarchy_level': 'staff',
                'can_assign_roles': False,
                'requires_gm_approval': True
            }
        ]
        
        for role_data in roles_data:
            if not dry_run:
                role, created = EmployeeRole.objects.get_or_create(
                    name=role_data['name'],
                    defaults=role_data
                )
                if created:
                    self.stdout.write(f'Created role: {role.display_name}')
                else:
                    self.stdout.write(f'Role exists: {role.display_name}')
            else:
                self.stdout.write(f'Would create role: {role_data["display_name"]}')

    def migrate_users_to_roles(self, dry_run):
        """Assign roles to users based on their current profiles"""
        users = User.objects.filter(profile__isnull=False).select_related('profile')
        
        role_mapping = {
            'it_admin': 'system_admin',
            'general_manager': 'business_owner',
            'sales_manager': 'sales_manager',
            'sales_rep': 'sales_rep',
            'employee': 'sales_rep',  # Default mapping
        }
        
        for user in users:
            profile = user.profile
            if profile.user_type in role_mapping:
                role_name = role_mapping[profile.user_type]
                
                if not dry_run:
                    try:
                        role = EmployeeRole.objects.get(name=role_name)
                        user_role, created = UserRole.objects.get_or_create(
                            user=user,
                            role=role,
                            defaults={'is_active': True}
                        )
                        if created:
                            self.stdout.write(f'Assigned {role_name} to {user.username}')
                        else:
                            self.stdout.write(f'{user.username} already has {role_name}')
                    except EmployeeRole.DoesNotExist:
                        self.stdout.write(f'Role {role_name} not found for {user.username}')
                else:
                    self.stdout.write(f'Would assign {role_name} to {user.username}')

    def setup_role_permissions(self, dry_run):
        """Set up default permissions for roles"""
        permissions_data = {
            'business_owner': {
                'crm': 'admin', 'inventory': 'admin', 'shop': 'admin',
                'website': 'admin', 'blog': 'admin', 'hr': 'admin',
                'admin': 'admin', 'quotes': 'admin', 'financial': 'admin',
                'reports': 'admin'
            },
            'system_admin': {
                'crm': 'admin', 'inventory': 'admin', 'shop': 'admin',
                'website': 'admin', 'hr': 'admin', 'admin': 'admin',
                'quotes': 'admin', 'financial': 'view', 'reports': 'admin'
            },
            'sales_manager': {
                'crm': 'admin', 'quotes': 'admin', 'reports': 'view',
                'website': 'edit', 'shop': 'view'
            },
            'sales_rep': {
                'crm': 'edit', 'quotes': 'edit', 'shop': 'view'
            },
            'procurement_officer': {
                'inventory': 'admin', 'crm': 'view', 'reports': 'view'
            }
        }
        
        for role_name, permissions in permissions_data.items():
            if not dry_run:
                try:
                    role = EmployeeRole.objects.get(name=role_name)
                    for app, level in permissions.items():
                        perm, created = AppPermission.objects.get_or_create(
                            role=role,
                            app=app,
                            defaults={'permission_level': level}
                        )
                        if created:
                            self.stdout.write(f'Created {app}:{level} for {role_name}')
                except EmployeeRole.DoesNotExist:
                    self.stdout.write(f'Role {role_name} not found')
            else:
                self.stdout.write(f'Would create permissions for {role_name}: {permissions}')
