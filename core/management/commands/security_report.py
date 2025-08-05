# core/management/commands/security_report.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
from core.models import SecurityEvent, UserProfile, ApprovalRequest
import logging

logger = logging.getLogger('core.management')

class Command(BaseCommand):
    help = 'Generate security and user activity report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for the report (default: 7)'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export report to file (specify filename)'
        )

    def handle(self, *args, **options):
        days = options['days']
        export_file = options['export']
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        report_lines = []
        
        def add_line(line):
            self.stdout.write(line)
            report_lines.append(line)
        
        add_line("="*60)
        add_line(f"BLITZTECH ELECTRONICS - SECURITY REPORT")
        add_line(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        add_line("="*60)
        
        # Security Events Summary
        add_line("\n📊 SECURITY EVENTS SUMMARY")
        add_line("-" * 30)
        
        security_events = SecurityEvent.objects.filter(
            timestamp__gte=start_date
        ).values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        total_events = sum(event['count'] for event in security_events)
        add_line(f"Total Security Events: {total_events}")
        
        for event in security_events:
            add_line(f"  - {event['event_type'].replace('_', ' ').title()}: {event['count']}")
        
        # Failed Login Analysis
        add_line("\n🚨 FAILED LOGIN ANALYSIS")
        add_line("-" * 30)
        
        failed_logins = SecurityEvent.objects.filter(
            event_type='login_failure',
            timestamp__gte=start_date
        ).values('ip_address').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        if failed_logins:
            add_line(f"Top Failed Login IPs:")
            for login in failed_logins:
                add_line(f"  - {login['ip_address']}: {login['count']} attempts")
        else:
            add_line("No failed login attempts recorded")
        
        # User Registration Activity
        add_line("\n👥 USER REGISTRATION ACTIVITY")
        add_line("-" * 30)
        
        new_users = UserProfile.objects.filter(
            date_joined__gte=start_date
        ).values('user_type').annotate(
            count=Count('id')
        )
        
        total_new_users = sum(user['count'] for user in new_users)
        add_line(f"Total New Users: {total_new_users}")
        
        for user_type in new_users:
            add_line(f"  - {user_type['user_type'].title()}: {user_type['count']}")
        
        # Approval Requests
        add_line("\n📋 APPROVAL REQUESTS")
        add_line("-" * 30)
        
        approvals = ApprovalRequest.objects.filter(
            requested_at__gte=start_date
        ).values('status', 'request_type').annotate(
            count=Count('id')
        )
        
        if approvals:
            for approval in approvals:
                add_line(
                    f"  - {approval['request_type'].upper()} "
                    f"({approval['status'].title()}): {approval['count']}"
                )
        else:
            add_line("No approval requests in this period")
        
        # Profile Completion Stats
        add_line("\n📝 PROFILE COMPLETION STATUS")
        add_line("-" * 30)
        
        completed_profiles = UserProfile.objects.filter(profile_completed=True).count()
        incomplete_profiles = UserProfile.objects.filter(profile_completed=False).count()
        total_profiles = completed_profiles + incomplete_profiles
        
        if total_profiles > 0:
            completion_rate = (completed_profiles / total_profiles) * 100
            add_line(f"Completed Profiles: {completed_profiles} ({completion_rate:.1f}%)")
            add_line(f"Incomplete Profiles: {incomplete_profiles}")
        
        # Suspicious Activity
        add_line("\n⚠️  SUSPICIOUS ACTIVITY")
        add_line("-" * 30)
        
        suspicious_events = SecurityEvent.objects.filter(
            event_type='suspicious_activity',
            timestamp__gte=start_date
        ).count()
        
        if suspicious_events > 0:
            add_line(f"Suspicious activities detected: {suspicious_events}")
            add_line("⚠️  Review these events manually")
        else:
            add_line("No suspicious activities detected")
        
        add_line("\n" + "="*60)
        add_line("Report generated at: " + timezone.now().strftime('%Y-%m-%d %H:%M:%S'))
        add_line("="*60)
        
        # Export to file if requested
        if export_file:
            try:
                with open(export_file, 'w') as f:
                    f.write('\n'.join(report_lines))
                
                self.stdout.write(
                    self.style.SUCCESS(f"\nReport exported to: {export_file}")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to export report: {str(e)}")
                )
        
        logger.info(f"Security report generated for {days} days")
