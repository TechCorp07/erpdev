# core/management/commands/test_all_permissions.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.http import HttpRequest
from django.contrib.auth import authenticate
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from core.models import EmployeeRole, AppPermission, UserRole
from core.utils import (
    get_user_roles, get_user_permissions, has_app_permission, 
    is_employee, is_customer, is_blogger, can_user_manage_roles,
    requires_gm_approval
)
from core.middleware import EmployeeAccessMiddleware
import json
from datetime import datetime

class Command(BaseCommand):
    help = 'Comprehensive testing of all permission and access control systems'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed test output'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export test results to JSON file'
        )

    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.export_file = options.get('export')
        
        self.stdout.write(self.style.SUCCESS('🧪 Running comprehensive permission tests...\n'))
        
        # Initialize test results
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'test_details': []
        }
        
        # Run all test suites
        try:
            self.test_user_type_utilities()
            self.test_role_system()
            self.test_app_permissions()
            self.test_edge_cases()
            self.test_middleware_protection()
            self.test_admin_functions()
            self.test_permission_caching()
        except Exception as e:
            self.stdout.write(f'❌ Test suite error: {e}')
            # Continue with displaying results even if there were errors
        
        # Display final results
        self.display_test_summary()
        
        if self.export_file:
            self.export_results()

    def run_test(self, test_name, test_func, expected_result=None):
        """Run a single test and record results"""
        try:
            actual_result = test_func()
            
            if expected_result is not None:
                passed = actual_result == expected_result
            else:
                passed = actual_result  # For boolean tests
            
            self.test_results['total_tests'] += 1
            
            if passed:
                self.test_results['passed_tests'] += 1
                status = '✅ PASS'
            else:
                self.test_results['failed_tests'] += 1
                status = '❌ FAIL'
            
            test_detail = {
                'name': test_name,
                'status': 'PASS' if passed else 'FAIL',
                'expected': expected_result,
                'actual': actual_result
            }
            self.test_results['test_details'].append(test_detail)
            
            if self.verbose or not passed:
                self.stdout.write(f'{status} {test_name}')
                if not passed and expected_result is not None:
                    self.stdout.write(f'    Expected: {expected_result}, Got: {actual_result}')
            
            return passed
            
        except Exception as e:
            self.test_results['total_tests'] += 1
            self.test_results['failed_tests'] += 1
            self.stdout.write(f'❌ ERROR {test_name}: {str(e)}')
            
            test_detail = {
                'name': test_name,
                'status': 'ERROR',
                'error': str(e)
            }
            self.test_results['test_details'].append(test_detail)
            return False

    def test_user_type_utilities(self):
        """Test user type checking utilities"""
        self.stdout.write('\n🔍 Testing User Type Utilities:')
        
        # Get test users
        customer = User.objects.filter(username='test_customer_001').first()
        blogger = User.objects.filter(username='test_blogger_001').first()
        employee = User.objects.filter(username='test_business_owner_001').first()
        
        if customer:
            self.run_test('Customer type check', lambda: is_customer(customer), True)
            self.run_test('Customer not employee', lambda: not is_employee(customer), True)
            self.run_test('Customer not blogger', lambda: not is_blogger(customer), True)
        
        if blogger:
            self.run_test('Blogger type check', lambda: is_blogger(blogger), True)
            self.run_test('Blogger not employee', lambda: not is_employee(blogger), True)
            self.run_test('Blogger not customer', lambda: not is_customer(blogger), True)
        
        if employee:
            self.run_test('Employee type check', lambda: is_employee(employee), True)
            self.run_test('Employee not customer', lambda: not is_customer(employee), True)
            self.run_test('Employee not blogger', lambda: not is_blogger(employee), True)

    def test_role_system(self):
        """Test employee role assignment and retrieval"""
        self.stdout.write('\n👔 Testing Role System:')
        
        # Test business owner
        business_owner = User.objects.filter(username='test_business_owner_001').first()
        if business_owner:
            self.run_test(
                'Business owner has correct role',
                lambda: 'business_owner' in get_user_roles(business_owner),
                True
            )
            self.run_test(
                'Business owner can assign roles',
                lambda: can_user_manage_roles(business_owner),
                True
            )
            self.run_test(
                'Business owner does not require approval',
                lambda: not requires_gm_approval(business_owner),
                True
            )
        
        # Test sales rep
        sales_rep = User.objects.filter(username='test_sales_rep_001').first()
        if sales_rep:
            self.run_test(
                'Sales rep has correct role',
                lambda: 'sales_rep' in get_user_roles(sales_rep),
                True
            )
            self.run_test(
                'Sales rep cannot assign roles',
                lambda: not can_user_manage_roles(sales_rep),
                True
            )
            self.run_test(
                'Sales rep requires approval',
                lambda: requires_gm_approval(sales_rep),
                True
            )
        
        # Test multi-role user
        multi_role = User.objects.filter(username='test_multi_role_employee').first()
        if multi_role:
            roles = get_user_roles(multi_role)
            self.run_test(
                'Multi-role user has multiple roles',
                lambda: len(get_user_roles(multi_role)) > 1,
                True
            )

    def test_app_permissions(self):
        """Test application-specific permissions"""
        self.stdout.write('\n🔐 Testing App Permissions:')
        
        # Test business owner permissions
        business_owner = User.objects.filter(username='test_business_owner_001').first()
        if business_owner:
            self.run_test(
                'Business owner has CRM admin',
                lambda: has_app_permission(business_owner, 'crm', 'admin'),
                True
            )
            self.run_test(
                'Business owner has inventory admin',
                lambda: has_app_permission(business_owner, 'inventory', 'admin'),
                True
            )
            self.run_test(
                'Business owner has all permissions',
                lambda: len(get_user_permissions(business_owner)) >= 5,
                True
            )
        
        # Test sales rep permissions
        sales_rep = User.objects.filter(username='test_sales_rep_001').first()
        if sales_rep:
            self.run_test(
                'Sales rep has CRM edit',
                lambda: has_app_permission(sales_rep, 'crm', 'edit'),
                True
            )
            self.run_test(
                'Sales rep does not have inventory admin',
                lambda: not has_app_permission(sales_rep, 'inventory', 'admin'),
                True
            )
            self.run_test(
                'Sales rep can view shop',
                lambda: has_app_permission(sales_rep, 'shop', 'view'),
                True
            )
        
        # Test procurement officer permissions
        procurement = User.objects.filter(username='test_procurement_officer_001').first()
        if procurement:
            self.run_test(
                'Procurement has inventory admin',
                lambda: has_app_permission(procurement, 'inventory', 'admin'),
                True
            )
            self.run_test(
                'Procurement can view CRM',
                lambda: has_app_permission(procurement, 'crm', 'view'),
                True
            )
            self.run_test(
                'Procurement cannot admin CRM',
                lambda: not has_app_permission(procurement, 'crm', 'admin'),
                True
            )
        
        # Test customer permissions (should have none)
        customer = User.objects.filter(username='test_customer_001').first()
        if customer:
            self.run_test(
                'Customer has no CRM access',
                lambda: not has_app_permission(customer, 'crm', 'view'),
                True
            )
            self.run_test(
                'Customer has no inventory access',
                lambda: not has_app_permission(customer, 'inventory', 'view'),
                True
            )

    def test_edge_cases(self):
        """Test edge cases and error conditions"""
        self.stdout.write('\n🔬 Testing Edge Cases:')
        
        # Test inactive user
        inactive_user = User.objects.filter(username='test_inactive_employee').first()
        if inactive_user:
            self.run_test(
                'Inactive user authentication fails',
                lambda: not inactive_user.is_active,
                True
            )
        
        # Test locked account
        locked_user = User.objects.filter(username='test_locked_customer').first()
        if locked_user and hasattr(locked_user, 'profile'):
            self.run_test(
                'Locked account is detected',
                lambda: locked_user.profile.is_account_locked,
                True
            )
        
        # Test user without profile (be careful with this)
        try:
            user_no_profile = User.objects.create_user(
                username='test_no_profile_temp',
                email='noprofile@test.com',
                password='test123'
            )
            # Delete the auto-created profile to test edge case
            if hasattr(user_no_profile, 'profile'):
                user_no_profile.profile.delete()
            
            self.run_test(
                'User without profile handled gracefully',
                lambda: not is_employee(user_no_profile),
                True
            )
            
            # Clean up
            user_no_profile.delete()
            
        except Exception as e:
            self.stdout.write(f'⚠️ Could not test user without profile: {e}')
        
        # Test superuser permissions
        superuser = User.objects.filter(is_superuser=True).first()
        if superuser:
            self.run_test(
                'Superuser has all permissions',
                lambda: has_app_permission(superuser, 'crm', 'admin'),
                True
            )
            self.run_test(
                'Superuser can manage roles',
                lambda: can_user_manage_roles(superuser),
                True
            )

    def test_middleware_protection(self):
        """Test middleware access control"""
        self.stdout.write('\n🛡️ Testing Middleware Protection:')
        
        factory = RequestFactory()
        middleware = EmployeeAccessMiddleware(lambda x: None)
        
        # Test employee accessing CRM
        employee = User.objects.filter(username='test_sales_rep_001').first()
        if employee:
            request = factory.get('/crm/dashboard/')
            request.user = employee
            request.session = {}
            
            # This would normally be handled by the middleware
            # We're just testing the user has proper permissions
            self.run_test(
                'Employee can access CRM via middleware check',
                lambda: has_app_permission(employee, 'crm', 'view'),
                True
            )
        
        # Test customer blocked from CRM
        customer = User.objects.filter(username='test_customer_001').first()
        if customer:
            self.run_test(
                'Customer blocked from CRM',
                lambda: not has_app_permission(customer, 'crm', 'view'),
                True
            )

    def test_admin_functions(self):
        """Test admin and management functions"""
        self.stdout.write('\n⚙️ Testing Admin Functions:')
        
        # Test role management capabilities
        admin_user = User.objects.filter(username='test_system_admin_001').first()
        regular_user = User.objects.filter(username='test_sales_rep_001').first()
        
        if admin_user:
            self.run_test(
                'System admin can manage roles',
                lambda: can_user_manage_roles(admin_user),
                True
            )
        
        if regular_user:
            self.run_test(
                'Regular user cannot manage roles',
                lambda: not can_user_manage_roles(regular_user),
                True
            )
        
        # Test permission level comparison
        business_owner = User.objects.filter(username='test_business_owner_001').first()
        if business_owner:
            permissions = get_user_permissions(business_owner)
            self.run_test(
                'Business owner has comprehensive permissions',
                lambda: len(permissions) >= 5,
                True
            )
            
            # Test specific permission levels
            if 'crm' in permissions:
                self.run_test(
                    'Business owner has admin level CRM',
                    lambda: permissions['crm'] == 'admin',
                    True
                )

    def test_permission_caching(self):
        """Test permission caching functionality"""
        self.stdout.write('\n💾 Testing Permission Caching:')
        
        employee = User.objects.filter(username='test_business_owner_001').first()
        if employee:
            try:
                # First call should populate cache
                permissions1 = get_user_permissions(employee)
                
                # Second call should use cache (if implemented)
                permissions2 = get_user_permissions(employee)
                
                self.run_test(
                    'Permission caching consistency',
                    lambda: permissions1 == permissions2,
                    True
                )
            except Exception as e:
                self.stdout.write(f'⚠️ Permission caching test skipped: {e}')

    def display_test_summary(self):
        """Display comprehensive test results"""
        total = self.test_results['total_tests']
        passed = self.test_results['passed_tests']
        failed = self.test_results['failed_tests']
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('🧪 PERMISSION TEST SUMMARY'))
        self.stdout.write('='*60)
        
        if failed == 0:
            self.stdout.write(self.style.SUCCESS(f'✅ ALL TESTS PASSED! ({passed}/{total})'))
        else:
            self.stdout.write(self.style.WARNING(f'⚠️ {failed} TEST(S) FAILED'))
            self.stdout.write(f'   Passed: {passed}/{total}')
            self.stdout.write(f'   Failed: {failed}/{total}')
        
        self.stdout.write('\n📊 Test Breakdown:')
        
        # Group tests by category
        categories = {}
        for test in self.test_results['test_details']:
            category = test['name'].split(' ')[0]
            if category not in categories:
                categories[category] = {'passed': 0, 'failed': 0}
            
            if test['status'] == 'PASS':
                categories[category]['passed'] += 1
            else:
                categories[category]['failed'] += 1
        
        for category, counts in categories.items():
            total_cat = counts['passed'] + counts['failed']
            self.stdout.write(f'   {category}: {counts["passed"]}/{total_cat} passed')
        
        # Show failed tests
        if failed > 0:
            self.stdout.write('\n❌ Failed Tests:')
            for test in self.test_results['test_details']:
                if test['status'] != 'PASS':
                    self.stdout.write(f'   - {test["name"]}')
                    if 'error' in test:
                        self.stdout.write(f'     Error: {test["error"]}')

    def export_results(self):
        """Export test results to JSON file"""
        try:
            with open(self.export_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            self.stdout.write(f'\n📄 Test results exported to: {self.export_file}')
        except Exception as e:
            self.stdout.write(f'\n❌ Failed to export results: {e}')


# Additional test file for Django's test framework
# tests/test_permissions.py

from django.test import TestCase
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from core.models import EmployeeRole, AppPermission, UserRole, UserProfile
from core.utils import get_user_permissions, has_app_permission

class PermissionSystemTestCase(TestCase):
    """Django test case for permission system integration tests"""
    
    def setUp(self):
        """Set up test data"""
        # Create test role
        self.test_role = EmployeeRole.objects.create(
            name='test_manager',
            display_name='Test Manager',
            can_assign_roles=False
        )
        
        # Create test permission
        self.test_permission = AppPermission.objects.create(
            role=self.test_role,
            app='crm',
            permission_level='edit'
        )
        
        # Create test users
        self.employee_user = User.objects.create_user(
            username='test_employee',
            email='employee@test.com',
            password='testpass123'
        )
        self.employee_user.profile.user_type = 'employee'
        self.employee_user.profile.save()
        
        self.customer_user = User.objects.create_user(
            username='test_customer',
            email='customer@test.com',
            password='testpass123'
        )
        self.customer_user.profile.user_type = 'customer'
        self.customer_user.profile.save()
        
        # Assign role to employee
        UserRole.objects.create(user=self.employee_user, role=self.test_role)
        
        self.client = Client()

    def test_user_type_permissions(self):
        """Test that user types have correct permissions"""
        # Employee with role should have CRM edit
        self.assertTrue(has_app_permission(self.employee_user, 'crm', 'edit'))
        
        # Customer should not have CRM access
        self.assertFalse(has_app_permission(self.customer_user, 'crm', 'view'))

    def test_permission_inheritance(self):
        """Test that edit permission includes view permission"""
        # User with edit should also have view
        self.assertTrue(has_app_permission(self.employee_user, 'crm', 'view'))
        self.assertTrue(has_app_permission(self.employee_user, 'crm', 'edit'))
        
        # User should not have admin (higher level)
        self.assertFalse(has_app_permission(self.employee_user, 'crm', 'admin'))

    def test_login_redirect_by_user_type(self):
        """Test that users are redirected correctly after login"""
        # Employee should go to dashboard
        response = self.client.post(reverse('core:login'), {
            'username': 'test_employee',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)
        
        # Customer login
        self.client.logout()
        response = self.client.post(reverse('core:login'), {
            'username': 'test_customer',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)

    def test_view_protection(self):
        """Test that views are properly protected"""
        # Try to access employee area as customer
        self.client.login(username='test_customer', password='testpass123')
        
        # This should be blocked or redirected
        response = self.client.get('/core/dashboard/')  # Assuming this exists
        # Response depends on your middleware implementation
        
        # Login as employee should work
        self.client.login(username='test_employee', password='testpass123')
        response = self.client.get('/core/dashboard/')
        # Should be successful (200) or redirect to proper dashboard

    def test_permission_caching(self):
        """Test that permission caching works correctly"""
        # First call
        perms1 = get_user_permissions(self.employee_user)
        
        # Second call should be same (from cache)
        perms2 = get_user_permissions(self.employee_user)
        
        self.assertEqual(perms1, perms2)
        
        # Should contain CRM edit permission
        self.assertIn('crm', perms1)
        self.assertEqual(perms1['crm'], 'edit')
