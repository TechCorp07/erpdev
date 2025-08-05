# core/management/commands/check_profile_completion.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile
from core.utils import create_notification
import logging

logger = logging.getLogger('core.management')

class Command(BaseCommand):
    help = 'Check and update profile completion status for all users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--notify-incomplete',
            action='store_true',
            help='Send notifications to users with incomplete profiles'
        )
        parser.add_argument(
            '--user-type',
            type=str,
            help='Check specific user type only'
        )

    def handle(self, *args, **options):
        notify_incomplete = options['notify_incomplete']
        user_type = options['user_type']
        
        # Build queryset
        queryset = UserProfile.objects.select_related('user')
        
        if user_type:
            queryset = queryset.filter(user_type=user_type)
        
        total_checked = 0
        updated_count = 0
        incomplete_count = 0
        
        for profile in queryset:
            total_checked += 1
            old_status = profile.profile_completed
            
            # Check profile completion
            new_status = profile.check_profile_completion()
            
            if old_status != new_status:
                updated_count += 1
                status_text = "completed" if new_status else "incomplete"
                self.stdout.write(
                    f"Updated {profile.user.username}: profile {status_text}"
                )
            
            if not new_status:
                incomplete_count += 1
                
                if notify_incomplete:
                    # Send notification about incomplete profile
                    incomplete_fields = profile.get_incomplete_fields()
                    
                    create_notification(
                        user=profile.user,
                        title="Complete Your Profile",
                        message=f"Please complete the following fields: {', '.join(incomplete_fields)}",
                        notification_type='info',
                        action_url='/auth/profile/complete/'
                    )
                    
                    self.stdout.write(
                        f"Sent completion reminder to {profile.user.username}"
                    )
        
        # Summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(f"Total profiles checked: {total_checked}")
        self.stdout.write(f"Status updates: {updated_count}")
        self.stdout.write(f"Incomplete profiles: {incomplete_count}")
        
        if notify_incomplete and incomplete_count > 0:
            self.stdout.write(f"Notifications sent: {incomplete_count}")
        
        self.stdout.write(self.style.SUCCESS("Profile completion check completed"))
        logger.info(f"Profile completion check: {total_checked} checked, {updated_count} updated")

