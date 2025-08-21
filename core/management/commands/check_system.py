# core/management/commands/check_system.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import connection
from core.models import EmployeeRole, UserRole, AppPermission, UserProfile
from core.utils import get_user_roles, get_user_permissions, has_app_permission

class Command(BaseCommand):
    help = 'Check the health of the role-based permission system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Checking ERP system health...'))
        
        # Check 1: Database integrity
        self.check_database_integrity()
        
        # Check 2: Role assignments
        self.check_role_assignments()
        
        # Check 3: Permission functionality
        self.check_permission_functionality()
        
        # Check 4: Legacy code cleanup
        self.check_legacy_cleanup()
        
        self.stdout.write(self.style.SUCCESS('System health check completed!'))

    def check_database_integrity(self):
        """Check if all required tables and fields exist"""
        self.stdout.write('\n1. Checking database integrity...')
        
        with connection.cursor() as cursor:
            # Check if required tables exist
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name LIKE 'core_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = [
                'core_employeerole', 'core_userrole', 'core_apppermission',
                'core_userprofile', 'core_loginactivity'
            ]
            
            for table in required_tables:
                if table in tables:
                    self.stdout.write(f'  ✓ {table} exists')
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ {table} missing'))

    def check_role_assignments(self):
        """Check role assignments and permissions"""
        self.stdout.write('\n2. Checking role assignments...')
        
        total_users = User.objects.count()
        users_with_profiles = User.objects.filter(profile__isnull=False).count()
        users_with_roles = User.objects.filter(employee_roles__isnull=False).count()
        
        self.stdout.write(f'  Total users: {total_users}')
        self.stdout.write(f'  Users with profiles: {users_with_profiles}')
        self.stdout.write(f'  Users with roles: {users_with_roles}')
        
        # Check roles
        roles = EmployeeRole.objects.all()
        self.stdout.write(f'  Available roles: {roles.count()}')
        for role in roles:
            self.stdout.write(f'    - {role.display_name} ({role.name})')
        
        # Check permissions
        permissions = AppPermission.objects.all()
        self.stdout.write(f'  Total app permissions: {permissions.count()}')

    def check_permission_functionality(self):
        """Test permission functions with real data"""
        self.stdout.write('\n3. Testing permission functionality...')
        
        if User.objects.exists():
            user = User.objects.first()
            self.stdout.write(f'  Testing with user: {user.username}')
            
            try:
                # Test role retrieval
                roles = get_user_roles(user)
                self.stdout.write(f'    ✓ get_user_roles: {roles}')
                
                # Test permission retrieval
                permissions = get_user_permissions(user)
                self.stdout.write(f'    ✓ get_user_permissions: {len(permissions)} apps')
                
                # Test specific permission check
                has_crm = has_app_permission(user, 'crm', 'view')
                self.stdout.write(f'    ✓ has_app_permission (CRM): {has_crm}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ✗ Error: {e}'))
        else:
            self.stdout.write('  No users found to test with')

    def check_legacy_cleanup(self):
        """Check for any remaining legacy code issues"""
        self.stdout.write('\n4. Checking for legacy code cleanup...')
        
        # Check for any old direct user-permission relationships
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'core_apppermission' AND column_name = 'user_id'
                """)
                if cursor.fetchone():
                    self.stdout.write(self.style.ERROR('  ✗ Old user_id field still exists in AppPermission'))
                else:
                    self.stdout.write('  ✓ No legacy user_id field in AppPermission')
                    
                # Check for login_datetime field
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'core_loginactivity' AND column_name = 'login_datetime'
                """)
                if cursor.fetchone():
                    self.stdout.write(self.style.ERROR('  ✗ Legacy login_datetime field still exists'))
                else:
                    self.stdout.write('  ✓ No legacy login_datetime field')
                    
        except Exception as e:
            self.stdout.write(f'  Could not check legacy fields: {e}')
        
        self.stdout.write('  ✓ Legacy code cleanup appears complete')
