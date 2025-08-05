# core/management/commands/send_approval_reminders.py
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import ApprovalRequest
import logging

logger = logging.getLogger('core.management')

class Command(BaseCommand):
    help = 'Send reminder emails to admins about pending approval requests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=2,
            help='Send reminders for requests older than N days (default: 2)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what emails would be sent without sending them'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find old pending requests
        old_requests = ApprovalRequest.objects.filter(
            status='pending',
            requested_at__lt=cutoff_date
        ).select_related('user')
        
        count = old_requests.count()
        
        if count == 0:
            self.stdout.write("No pending requests found for reminders")
            return
        
        # Get admin emails
        admin_emails = getattr(settings, 'APPROVAL_NOTIFICATION_EMAILS', [])
        
        if not admin_emails:
            admin_users = User.objects.filter(is_superuser=True)
            admin_emails = [user.email for user in admin_users if user.email]
        
        if not admin_emails:
            self.stdout.write(self.style.ERROR("No admin emails configured"))
            return
        
        self.stdout.write(f"Found {count} pending requests older than {days} days")
        
        if dry_run:
            self.stdout.write(f"Would send reminder to: {', '.join(admin_emails)}")
            for request in old_requests:
                self.stdout.write(
                    f"  - {request.user.username}: {request.get_request_type_display()} "
                    f"(requested {request.requested_at.strftime('%Y-%m-%d')})"
                )
        else:
            # Send reminder email
            subject = f"{settings.COMPANY_NAME} - Pending Approval Requests Reminder"
            
            context = {
                'requests': old_requests,
                'count': count,
                'days': days,
                'company_name': settings.COMPANY_NAME,
                'admin_url': f"{settings.SITE_URL}/auth/manage-approvals/",
            }
            
            # Render email
            message = render_to_string('core/emails/approval_reminder.txt', context)
            
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=False
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f"Reminder sent to {len(admin_emails)} admins")
                )
                logger.info(f"Sent approval reminder for {count} pending requests")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to send reminder: {str(e)}")
                )
                logger.error(f"Failed to send approval reminder: {str(e)}")
