# core/management/commands/test_login.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import RequestFactory
from core.utils import authenticate_user, log_security_event
from core.models import SecurityEvent, LoginActivity

class Command(BaseCommand):
    help = 'Test the login flow functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Username to test with',
            default='admin'
        )

    def handle(self, *args, **options):
        username = options['username']
        
        self.stdout.write(self.style.SUCCESS('Testing login system components...'))
        
        # Test 1: Check if user exists
        try:
            user = User.objects.get(username=username)
            self.stdout.write(f'✓ Found user: {user.username}')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'✗ User {username} does not exist'))
            return
        
        # Test 2: Check user profile
        if hasattr(user, 'profile'):
            profile = user.profile
            self.stdout.write(f'✓ User has profile: {profile.user_type}')
            self.stdout.write(f'  - Account locked: {profile.is_account_locked}')
            self.stdout.write(f'  - Failed login count: {profile.failed_login_count}')
        else:
            self.stdout.write(self.style.WARNING('⚠ User has no profile'))
        
        # Test 3: Test security event creation
        try:
            log_security_event(
                user=user,
                event_type='login_success',
                description='Test security event',
                ip_address='127.0.0.1',
                details={'test': True}
            )
            self.stdout.write('✓ Security event creation works')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Security event failed: {e}'))
        
        # Test 4: Check recent security events
        recent_events = SecurityEvent.objects.filter(user=user).order_by('-timestamp')[:5]
        self.stdout.write(f'✓ Recent security events: {recent_events.count()}')
        
        # Test 5: Check login activities
        recent_logins = LoginActivity.objects.filter(user=user).order_by('-timestamp')[:5]
        self.stdout.write(f'✓ Recent login activities: {recent_logins.count()}')
        
        # Test 6: Test account locking (if profile exists)
        if hasattr(user, 'profile'):
            try:
                # Test lock/unlock (don't actually lock, just test the method exists)
                if hasattr(user.profile, 'lock_account'):
                    self.stdout.write('✓ Profile lock_account method exists')
                else:
                    self.stdout.write(self.style.WARNING('⚠ Profile lock_account method missing'))
                    
                if hasattr(user.profile, 'is_account_locked'):
                    self.stdout.write('✓ Profile is_account_locked property exists')
                else:
                    self.stdout.write(self.style.WARNING('⚠ Profile is_account_locked property missing'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Account lock test failed: {e}'))
        
        # Test 7: Create a mock request for authenticate_user
        try:
            factory = RequestFactory()
            request = factory.post('/auth/login/', {
                'username': username,
                'password': 'test'  # This will fail, but we're testing the function doesn't crash
            })
            request.META['REMOTE_ADDR'] = '127.0.0.1'
            request.META['HTTP_USER_AGENT'] = 'Test Agent'
            
            # This should not crash even with wrong password
            result = authenticate_user(request, username, 'wrongpassword', False)
            if result is None:
                self.stdout.write('✓ authenticate_user handles wrong password correctly')
            else:
                self.stdout.write('⚠ authenticate_user returned user with wrong password')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ authenticate_user test failed: {e}'))
        
        self.stdout.write(self.style.SUCCESS('Login system test completed!'))
