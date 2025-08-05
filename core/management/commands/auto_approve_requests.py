# core/management/commands/auto_approve_requests.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from core.models import ApprovalRequest
import logging

logger = logging.getLogger('core.management')

class Command(BaseCommand):
    help = 'Auto-approve old approval requests based on business rules'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be approved without actually approving'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        approval_settings = getattr(settings, 'APPROVAL_WORKFLOW', {})
        
        auto_approved = 0
        
        for user_type, config in approval_settings.items():
            auto_approve_hours = config.get('auto_approve_after_hours')
            
            if not auto_approve_hours:
                continue
            
            cutoff_time = timezone.now() - timedelta(hours=auto_approve_hours)
            
            # Find old pending requests for this user type
            old_requests = ApprovalRequest.objects.filter(
                user__profile__user_type=user_type,
                status='pending',
                requested_at__lt=cutoff_time
            )
            
            count = old_requests.count()
            
            if count > 0:
                self.stdout.write(
                    f"Found {count} old {user_type} requests (>{auto_approve_hours}h old)"
                )
                
                if dry_run:
                    for request in old_requests:
                        self.stdout.write(
                            f"  Would auto-approve: {request.user.username} - {request.get_request_type_display()}"
                        )
                else:
                    # Auto-approve them
                    for request in old_requests:
                        request.approve(
                            reviewer=None,  # System approval
                            notes=f"Auto-approved after {auto_approve_hours} hours"
                        )
                        auto_approved += 1
                        
                        self.stdout.write(
                            f"  Auto-approved: {request.user.username} - {request.get_request_type_display()}"
                        )
        
        if auto_approved > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Auto-approved {auto_approved} requests")
            )
            logger.info(f"Auto-approved {auto_approved} old approval requests")
        elif not dry_run:
            self.stdout.write("No requests found for auto-approval")
