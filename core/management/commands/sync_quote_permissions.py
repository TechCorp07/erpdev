# core/management/commands/sync_quote_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import UserProfile, AppPermission
from core.utils import invalidate_permission_cache

class Command(BaseCommand):
    help = 'Synchronize quote permissions based on user roles'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Sync permissions for specific user (username)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )
    
    def handle(self, *args, **options):
        if options['user']:
            users = User.objects.filter(username=options['user'])
            if not users.exists():
                self.stdout.write(
                    self.style.ERROR(f"User '{options['user']}' not found")
                )
                return
        else:
            users = User.objects.filter(is_active=True)
        
        changes_made = 0
        
        with transaction.atomic():
            for user in users:
                if hasattr(user, 'profile'):
                    changes = self.sync_user_permissions(user, options['dry_run'])
                    changes_made += changes
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would make {changes_made} permission changes')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Synchronized permissions for {users.count()} users, made {changes_made} changes')
            )
    
    def sync_user_permissions(self, user, dry_run=False):
        """Sync permissions for a single user based on their role"""
        from core.utils import setup_default_user_permissions
        
        changes = 0
        user_type = user.profile.user_type
        
        # Define expected permissions for each role
        expected_permissions = {
            'sales_rep': {'quotes': 'edit', 'crm': 'edit', 'financial': 'view', 'reports': 'view'},
            'sales_manager': {'quotes': 'admin', 'crm': 'admin', 'financial': 'edit', 'reports': 'admin'},
            'employee': {'quotes': 'view', 'crm': 'view', 'financial': 'view', 'reports': 'view'},
            'blitzhub_admin': {'quotes': 'admin', 'crm': 'admin', 'financial': 'admin', 'reports': 'admin'},
            'it_admin': {'quotes': 'admin', 'crm': 'admin', 'financial': 'view', 'reports': 'admin'},
        }
        
        if user_type not in expected_permissions:
            return 0
        
        expected = expected_permissions[user_type]
        current_permissions = {
            perm.app: perm.permission_level 
            for perm in AppPermission.objects.filter(user=user)
        }
        
        for app, expected_level in expected.items():
            current_level = current_permissions.get(app)
            
            if current_level != expected_level:
                self.stdout.write(
                    f"  {user.username}: {app} {current_level or 'None'} -> {expected_level}"
                )
                
                if not dry_run:
                    AppPermission.objects.update_or_create(
                        user=user,
                        app=app,
                        defaults={'permission_level': expected_level}
                    )
                    invalidate_permission_cache(user.id)
                
                changes += 1
        
        return changes
