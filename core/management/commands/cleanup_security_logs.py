# core/management/commands/cleanup_security_logs.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core import models
from core.models import SecurityEvent
import logging

logger = logging.getLogger('core.management')

class Command(BaseCommand):
    help = 'Clean up old security logs to maintain database performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to keep security logs (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f"Looking for security events older than {days} days ({cutoff_date})")
        
        # Find old security events
        old_events = SecurityEvent.objects.filter(timestamp__lt=cutoff_date)
        count = old_events.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No old security events found"))
            return
        
        if dry_run:
            self.stdout.write(f"Would delete {count} security events (dry run)")
            # Show breakdown by event type
            event_breakdown = old_events.values('event_type').annotate(
                count=models.Count('id')
            ).order_by('-count')
            
            for item in event_breakdown:
                self.stdout.write(f"  - {item['event_type']}: {item['count']} events")
        else:
            # Actually delete the events
            deleted_count, _ = old_events.delete()
            
            self.stdout.write(
                self.style.SUCCESS(f"Successfully deleted {deleted_count} old security events")
            )
            
            # Log the cleanup
            logger.info(f"Cleaned up {deleted_count} security events older than {days} days")
