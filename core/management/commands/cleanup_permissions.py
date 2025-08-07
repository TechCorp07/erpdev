# core/management/commands/cleanup_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, UserRole
from core.utils import invalidate_permission_cache

class Command(BaseCommand):
    help = 'Clean up permission cache and fix inconsistencies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-profiles',
            action='store_true',
            help='Fix user profiles with missing data',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear all permission caches',
        )

    def handle(self, *args, **options):
        if options['clear_cache']:
            self.clear_permission_cache()

        if options['fix_profiles']:
            self.fix_user_profiles()

        self.stdout.write(
            self.style.SUCCESS('Permission cleanup complete!')
        )

    def clear_permission_cache(self):
        """Clear all permission-related caches"""
        self.stdout.write("Clearing permission cache...")
        invalidate_permission_cache()
        self.stdout.write(self.style.SUCCESS("Permission cache cleared"))

    def fix_user_profiles(self):
        """Fix user profiles with missing or inconsistent data"""
        self.stdout.write("Fixing user profiles...")

        fixed_count = 0

        for user in User.objects.all():
            fixed = False

            # Ensure all users have profiles
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(user=user)
                fixed = True
                self.stdout.write(f"  Created profile for {user.username}")

            # Fix employee users without roles
            elif user.profile.is_employee and not user.employee_roles.filter(is_active=True).exists():
                self.stdout.write(
                    self.style.WARNING(f"  Employee {user.username} has no active roles")
                )
                # You could auto-assign a default role here if desired

            # Check profile completion
            if hasattr(user, 'profile'):
                user.profile.check_profile_completion()
                if user.profile.profile_completed:
                    fixed = True

            if fixed:
                fixed_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Fixed {fixed_count} user profiles")
        )