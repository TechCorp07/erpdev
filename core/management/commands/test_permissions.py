# core/management/commands/test_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.utils import get_user_roles, get_user_permissions, has_app_permission
from core.models import EmployeeRole, AppPermission, UserRole

class Command(BaseCommand):
    help = 'Test the role-based permission system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing role-based permission system...'))
        
        # Test 1: Check if roles exist
        roles = EmployeeRole.objects.all()
        self.stdout.write(f'Available roles: {list(roles.values_list("name", flat=True))}')
        
        # Test 2: Check if permissions exist
        permissions = AppPermission.objects.all()
        self.stdout.write(f'Total app permissions: {permissions.count()}')
        
        # Test 3: Test a specific user if exists
        if User.objects.exists():
            user = User.objects.first()
            self.stdout.write(f'\nTesting user: {user.username}')
            
            # Test role retrieval
            user_roles = get_user_roles(user)
            self.stdout.write(f'User roles: {user_roles}')
            
            # Test permission retrieval
            user_permissions = get_user_permissions(user)
            self.stdout.write(f'User permissions: {user_permissions}')
            
            # Test specific permission checks
            has_crm = has_app_permission(user, 'crm', 'view')
            has_quotes = has_app_permission(user, 'quotes', 'edit')
            
            self.stdout.write(f'Has CRM view: {has_crm}')
            self.stdout.write(f'Has Quotes edit: {has_quotes}')
        
        self.stdout.write(self.style.SUCCESS('Permission system test completed!'))
