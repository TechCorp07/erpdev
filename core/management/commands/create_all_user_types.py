# core/management/commands/create_all_user_types.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from core.models import UserProfile, EmployeeRole, AppPermission, UserRole, ApprovalRequest
from django.utils import timezone
import random

class Command(BaseCommand):
    help = 'Create comprehensive test users for all user types, roles, and permission levels'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', 
            type=int, 
            default=3,
            help='Number of users to create per user type (default: 3)'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete existing test users before creating new ones'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='TestPassword123!',
            help='Password for all test users (default: TestPassword123!)'
        )

    def handle(self, *args, **options):
        count = options['count']
        password = options['password']
        clean = options['clean']
        
        self.stdout.write(self.style.SUCCESS(f'Creating comprehensive test users...'))
        
        if clean:
            self.clean_test_users()
        
        with transaction.atomic():
            # 1. Create Employee Roles if they don't exist
            self.create_employee_roles()
            
            # 2. Create App Permissions for roles
            self.create_app_permissions()
            
            # 3. Create test users for each type
            self.create_customer_users(count, password)
            self.create_blogger_users(count, password)
            self.create_employee_users(count, password)
            
            # 4. Create edge case users
            self.create_edge_case_users(password)
            
        self.stdout.write(self.style.SUCCESS('\n✅ All test users created successfully!'))
        self.display_login_credentials(password)

    def clean_test_users(self):
        """Remove existing test users"""
        test_users = User.objects.filter(username__startswith='test_')
        count = test_users.count()
        test_users.delete()
        self.stdout.write(f'🧹 Deleted {count} existing test users')

    def create_employee_roles(self):
        """Create all employee roles"""
        roles_data = [
            {
                'name': 'business_owner',
                'display_name': 'Business Owner',
                'can_assign_roles': True,
                'requires_gm_approval': False,
                'description': 'Full business ownership and management'
            },
            {
                'name': 'system_admin',
                'display_name': 'System Administrator',
                'can_assign_roles': True,
                'requires_gm_approval': False,
                'description': 'Technical system administration and IT management'
            },
            {
                'name': 'sales_manager',
                'display_name': 'Sales Manager',
                'can_assign_roles': False,
                'requires_gm_approval': False,
                'description': 'Sales team leadership and strategy'
            },
            {
                'name': 'sales_rep',
                'display_name': 'Sales Representative',
                'can_assign_roles': False,
                'requires_gm_approval': True,
                'description': 'Direct sales and customer relations'
            },
            {
                'name': 'procurement_officer',
                'display_name': 'Procurement Officer',
                'can_assign_roles': False,
                'requires_gm_approval': True,
                'description': 'Inventory and supplier management'
            },
            {
                'name': 'finance_manager',
                'display_name': 'Finance Manager',
                'can_assign_roles': False,
                'requires_gm_approval': False,
                'description': 'Financial oversight and accounting'
            },
            {
                'name': 'support_agent',
                'display_name': 'Support Agent',
                'can_assign_roles': False,
                'requires_gm_approval': True,
                'description': 'Customer support and service'
            }
        ]
        
        for role_data in roles_data:
            role, created = EmployeeRole.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                self.stdout.write(f'✓ Created role: {role.display_name}')

    def create_app_permissions(self):
        """Create comprehensive app permissions for all roles"""
        permissions_map = {
            'business_owner': {
                'crm': 'admin', 'inventory': 'admin', 'shop': 'admin',
                'website': 'admin', 'blog': 'admin', 'hr': 'admin',
                'admin': 'admin', 'quotes': 'admin', 'financial': 'admin',
                'reports': 'admin'
            },
            'system_admin': {
                'crm': 'admin', 'inventory': 'admin', 'shop': 'admin',
                'website': 'admin', 'hr': 'admin', 'admin': 'admin',
                'quotes': 'edit', 'financial': 'view', 'reports': 'admin'
            },
            'sales_manager': {
                'crm': 'admin', 'quotes': 'admin', 'reports': 'edit',
                'website': 'edit', 'shop': 'edit', 'inventory': 'view'
            },
            'sales_rep': {
                'crm': 'edit', 'quotes': 'edit', 'shop': 'view',
                'reports': 'view'
            },
            'procurement_officer': {
                'inventory': 'admin', 'crm': 'view', 'reports': 'view',
                'quotes': 'view', 'shop': 'edit'
            },
            'finance_manager': {
                'financial': 'admin', 'reports': 'admin', 'crm': 'view',
                'quotes': 'view', 'inventory': 'view'
            },
            'support_agent': {
                'crm': 'edit', 'shop': 'view', 'website': 'view'
            }
        }
        
        for role_name, permissions in permissions_map.items():
            try:
                role = EmployeeRole.objects.get(name=role_name)
                for app, level in permissions.items():
                    perm, created = AppPermission.objects.get_or_create(
                        role=role,
                        app=app,
                        defaults={'permission_level': level}
                    )
                    if created:
                        self.stdout.write(f'✓ Created permission: {role_name} -> {app}:{level}')
            except EmployeeRole.DoesNotExist:
                self.stdout.write(f'⚠️ Role {role_name} not found')

    def create_customer_users(self, count, password):
        """Create customer users with various configurations"""
        self.stdout.write(f'\n👥 Creating {count} Customer users...')
        
        for i in range(count):
            username = f'test_customer_{i+1:03d}'
            email = f'customer{i+1:03d}@blitztech-test.com'
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=f'Customer',
                last_name=f'Test{i+1:03d}'
            )
            
            # Configure customer profile
            profile = user.profile
            profile.user_type = 'customer'
            profile.phone = f'+263{77}{2000000 + i:07d}'
            profile.address = f'{i+1} Customer Ave, Harare, Zimbabwe'
            profile.billing_address = profile.address
            profile.company_name = f'Test Company {i+1:03d}' if i % 2 == 0 else ''
            profile.shop_approved = True
            profile.profile_completed = True
            profile.save()
            
            self.stdout.write(f'✓ Created customer: {username}')

    def create_blogger_users(self, count, password):
        """Create blogger users with approval requests"""
        self.stdout.write(f'\n📝 Creating {count} Blogger users...')
        
        for i in range(count):
            username = f'test_blogger_{i+1:03d}'
            email = f'blogger{i+1:03d}@blitztech-test.com'
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=f'Blogger',
                last_name=f'Test{i+1:03d}'
            )
            
            # Configure blogger profile
            profile = user.profile
            profile.user_type = 'blogger'
            profile.phone = f'+263{78}{3000000 + i:07d}'
            profile.address = f'{i+1} Blogger Street, Bulawayo, Zimbabwe'
            profile.shop_approved = True
            profile.blog_approved = i % 2 == 0  # Half approved, half pending
            profile.profile_completed = True
            profile.save()
            
            # Create approval requests for blog access
            if not profile.blog_approved:
                ApprovalRequest.objects.create(
                    user=user,
                    request_type='blog',
                    status='pending',
                    requested_reason=f'Test blogger {i+1} requesting blog management access',
                    business_justification='Content creation for testing workflow'
                )
            
            self.stdout.write(f'✓ Created blogger: {username}')

    def create_employee_users(self, count, password):
        """Create employee users with different roles and departments"""
        self.stdout.write(f'\n💼 Creating {count} Employee users per role...')
        
        roles = EmployeeRole.objects.all()
        departments = ['sales', 'technical', 'admin', 'procurement', 'finance', 'support', 'it']
        
        for role in roles:
            for i in range(count):
                username = f'test_{role.name}_{i+1:03d}'
                email = f'{role.name}{i+1:03d}@blitztech-test.com'
                
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=role.display_name.split()[0],
                    last_name=f'Test{i+1:03d}'
                )
                
                # Configure employee profile
                profile = user.profile
                profile.user_type = 'employee'
                profile.department = random.choice(departments)
                profile.phone = f'+263{71}{4000000 + len(username):07d}'
                profile.address = f'{i+1} Employee Road, Harare, Zimbabwe'
                profile.profile_completed = True
                profile.save()
                
                # Assign role to employee
                UserRole.objects.create(user=user, role=role)
                
                self.stdout.write(f'✓ Created employee: {username} ({role.display_name})')

    def create_edge_case_users(self, password):
        """Create users for testing edge cases"""
        self.stdout.write(f'\n🔬 Creating edge case users...')
        
        edge_cases = [
            {
                'username': 'test_inactive_employee',
                'email': 'inactive@blitztech-test.com',
                'user_type': 'employee',
                'is_active': False,
                'first_name': 'Inactive',
                'last_name': 'Employee'
            },
            {
                'username': 'test_locked_customer',
                'email': 'locked@blitztech-test.com',
                'user_type': 'customer',
                'is_account_locked': True,
                'first_name': 'Locked',
                'last_name': 'Customer'
            },
            {
                'username': 'test_multi_role_employee',
                'email': 'multirole@blitztech-test.com',
                'user_type': 'employee',
                'first_name': 'Multi',
                'last_name': 'Role'
            },
            {
                'username': 'test_customer_blogger',
                'email': 'custblogger@blitztech-test.com',
                'user_type': 'customer',  # Customer who is also a blogger
                'first_name': 'CustomerBlogger',
                'last_name': 'Test'
            }
        ]
        
        for case in edge_cases:
            user = User.objects.create_user(
                username=case['username'],
                email=case['email'],
                password=password,
                first_name=case['first_name'],
                last_name=case['last_name'],
                is_active=case.get('is_active', True)
            )
            
            profile = user.profile
            profile.user_type = case['user_type']
            profile.phone = '+263712345678'
            profile.address = 'Test Address, Harare'
            profile.profile_completed = True
            
            if case.get('is_account_locked'):
                # Use the lock_account method instead of setting property directly
                profile.lock_account(minutes=60)  # Lock for 1 hour
            
            profile.save()
            
            # Special configurations
            if case['username'] == 'test_multi_role_employee':
                # Assign multiple roles
                sales_role = EmployeeRole.objects.filter(name='sales_rep').first()
                support_role = EmployeeRole.objects.filter(name='support_agent').first()
                if sales_role:
                    UserRole.objects.create(user=user, role=sales_role)
                if support_role:
                    UserRole.objects.create(user=user, role=support_role)
            
            elif case['username'] == 'test_customer_blogger':
                # Customer who also has blog approval request
                ApprovalRequest.objects.create(
                    user=user,
                    request_type='blog',
                    status='approved',
                    requested_reason='Customer requesting blog access',
                    business_justification='Customer wants to write reviews'
                )
            
            self.stdout.write(f'✓ Created edge case: {case["username"]}')

    def display_login_credentials(self, password):
        """Display login information for all created users"""
        self.stdout.write(self.style.SUCCESS('\n🔐 Login Credentials for all test users:'))
        self.stdout.write(f'Password for all users: {password}')
        self.stdout.write('\n📝 Username patterns:')
        self.stdout.write('  Customers: test_customer_001, test_customer_002, test_customer_003')
        self.stdout.write('  Bloggers: test_blogger_001, test_blogger_002, test_blogger_003')
        self.stdout.write('  Employees: test_business_owner_001, test_sales_manager_001, etc.')
        self.stdout.write('  Edge cases: test_inactive_employee, test_locked_customer, etc.')
        
        self.stdout.write('\n🎯 Quick test users:')
        self.stdout.write(f'  Admin access: test_business_owner_001 / {password}')
        self.stdout.write(f'  Sales manager: test_sales_manager_001 / {password}')
        self.stdout.write(f'  Customer: test_customer_001 / {password}')
        self.stdout.write(f'  Blogger: test_blogger_001 / {password}')
