"""
CRM utility functions and integration helpers
"""
from django.db.models import Q, Count, Sum, Avg, F
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.contrib.auth.models import User
from core.utils import create_notification
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CRMAnalytics:
    """Class for CRM analytics and reporting"""
    
    @staticmethod
    def get_client_acquisition_data(days=30):
        """Get client acquisition data for the last N days"""
        from .models import Client
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        data = Client.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).extra(
            select={'date': "DATE(created_at)"}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return list(data)
    
    @staticmethod
    def get_status_distribution():
        """Get client status distribution"""
        from .models import Client
        
        return Client.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
    
    @staticmethod
    def get_customer_type_distribution():
        """Get customer type distribution"""
        from .models import Client
        
        return Client.objects.values('customer_type').annotate(
            count=Count('id')
        ).order_by('-count')
    
    @staticmethod
    def get_regional_distribution():
        """Get regional client distribution"""
        from .models import Client
        
        return Client.objects.exclude(
            country__isnull=True
        ).exclude(
            country=''
        ).values('country').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
    
    @staticmethod
    def get_interaction_trends(days=30):
        """Get interaction trends for the last N days"""
        from .models import CustomerInteraction
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        data = CustomerInteraction.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).extra(
            select={'date': "DATE(created_at)"}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        return list(data)
    
    @staticmethod
    def get_top_clients_by_interactions(limit=10):
        """Get top clients by interaction count"""
        from .models import Client
        
        return Client.objects.annotate(
            interaction_count=Count('customerinteraction')
        ).filter(
            interaction_count__gt=0
        ).order_by('-interaction_count')[:limit]
    
    @staticmethod
    def get_performance_metrics():
        """Get key performance metrics"""
        from .models import Client, CustomerInteraction
        
        total_clients = Client.objects.count()
        active_clients = Client.objects.filter(status__in=['prospect', 'client']).count()
        total_interactions = CustomerInteraction.objects.count()
        
        # Calculate average interactions per client
        avg_interactions = (total_interactions / total_clients) if total_clients > 0 else 0
        
        # Calculate conversion rate (prospects to clients)
        prospects = Client.objects.filter(status='prospect').count()
        clients = Client.objects.filter(status='client').count()
        conversion_rate = (clients / (prospects + clients) * 100) if (prospects + clients) > 0 else 0
        
        return {
            'total_clients': total_clients,
            'active_clients': active_clients,
            'total_interactions': total_interactions,
            'avg_interactions_per_client': round(avg_interactions, 1),
            'conversion_rate': round(conversion_rate, 1),
        }


class CRMAutomation:
    """Class for CRM automation tasks"""
    
    @staticmethod
    def update_lead_scores():
        """Update lead scores for all clients"""
        from .models import Client
        
        updated_count = 0
        for client in Client.objects.filter(status__in=['lead', 'prospect']):
            old_score = client.lead_score
            new_score = client.calculate_lead_score()
            
            if abs(old_score - new_score) > 5:  # Significant change
                logger.info(f"Lead score updated for {client.name}: {old_score} -> {new_score}")
                updated_count += 1
        
        return updated_count
    
    @staticmethod
    def check_overdue_followups():
        """Check for overdue follow-ups and send notifications"""
        from .models import CustomerInteraction
        
        overdue_interactions = CustomerInteraction.objects.filter(
            next_followup__lt=timezone.now(),
            next_followup__isnull=False
        ).select_related('client', 'created_by')
        
        # Group by user for batch notifications
        user_overdue = {}
        for interaction in overdue_interactions:
            if interaction.created_by:
                if interaction.created_by not in user_overdue:
                    user_overdue[interaction.created_by] = []
                user_overdue[interaction.created_by].append(interaction)
        
        # Send notifications
        for user, interactions in user_overdue.items():
            count = len(interactions)
            if count > 0:
                create_notification(
                    user=user,
                    title=f"{count} Overdue Follow-up{'s' if count > 1 else ''}",
                    message=f"You have {count} overdue follow-up{'s' if count > 1 else ''} that need attention.",
                    notification_type="warning"
                )
        
        return len(overdue_interactions)
    
    @staticmethod
    def auto_assign_leads():
        """Auto-assign unassigned leads to available team members"""
        from .models import Client
        from core.models import UserProfile
        
        # Get unassigned leads
        unassigned_leads = Client.objects.filter(
            status='lead',
            assigned_to__isnull=True
        )
        
        # Get available sales team members
        sales_team = User.objects.filter(
            profile__user_type__in=['employee', 'blitzhub_admin'],
            profile__department='sales',
            is_active=True
        )
        
        if not sales_team.exists():
            return 0
        
        assigned_count = 0
        for i, lead in enumerate(unassigned_leads):
            # Round-robin assignment
            assignee = sales_team[i % sales_team.count()]
            lead.assigned_to = assignee
            lead.save()
            
            # Notify the assignee
            create_notification(
                user=assignee,
                title="New Lead Assigned",
                message=f"You have been assigned a new lead: {lead.name}",
                notification_type="info"
            )
            
            assigned_count += 1
        
        return assigned_count
    
    @staticmethod
    def cleanup_old_data(days=365):
        """Clean up old CRM data"""
        from .models import CustomerInteraction, Task, ClientNote
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clean up old completed tasks
        old_tasks = Task.objects.filter(
            status='completed',
            completed_at__lt=cutoff_date
        )
        task_count = old_tasks.count()
        old_tasks.delete()
        
        # Archive old interactions (don't delete, but could mark as archived)
        old_interactions = CustomerInteraction.objects.filter(
            created_at__lt=cutoff_date
        )
        interaction_count = old_interactions.count()
        
        logger.info(f"Cleaned up {task_count} old tasks and found {interaction_count} old interactions")
        
        return {
            'tasks_deleted': task_count,
            'old_interactions': interaction_count
        }


class CRMIntegrationUtils:
    """Utilities for integrating CRM with other systems"""
    
    @staticmethod
    def migrate_legacy_clients(legacy_clients_data):
        """Migrate clients from legacy system"""
        from .models import Client
        
        migrated_count = 0
        errors = []
        
        for data in legacy_clients_data:
            try:
                # Check if client already exists
                if Client.objects.filter(email=data.get('email')).exists():
                    continue
                
                client = Client.objects.create(
                    name=data.get('name', ''),
                    email=data.get('email', ''),
                    phone=data.get('phone', ''),
                    company=data.get('company', ''),
                    status=data.get('status', 'lead'),
                    customer_type=data.get('customer_type', 'walk_in'),
                    notes=data.get('notes', ''),
                    # Map other fields as needed
                )
                
                migrated_count += 1
                logger.info(f"Migrated client: {client.name}")
                
            except Exception as e:
                error_msg = f"Error migrating client {data.get('name', 'Unknown')}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        return {
            'migrated_count': migrated_count,
            'errors': errors
        }
    
    @staticmethod
    def sync_with_external_system(api_endpoint, api_key):
        """Sync CRM data with external system"""
        # This would implement API integration with external systems
        # like accounting software, email marketing, etc.
        pass
    
    @staticmethod
    def export_clients_to_csv():
        """Export clients to CSV format"""
        from .models import Client
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Name', 'Email', 'Phone', 'Company', 'Status', 
            'Customer Type', 'Country', 'Created Date', 'Last Contacted'
        ])
        
        # Write data
        for client in Client.objects.all():
            writer.writerow([
                client.name,
                client.email,
                client.phone or '',
                client.company or '',
                client.get_status_display(),
                client.get_customer_type_display(),
                client.country or '',
                client.created_at.strftime('%Y-%m-%d'),
                client.last_contacted.strftime('%Y-%m-%d') if client.last_contacted else ''
            ])
        
        return output.getvalue()


class CRMCacheUtils:
    """Utilities for CRM caching"""
    
    @staticmethod
    def get_cached_analytics(cache_key, calculation_func, timeout=300):
        """Get analytics data from cache or calculate and cache"""
        data = cache.get(cache_key)
        if data is None:
            data = calculation_func()
            cache.set(cache_key, data, timeout)
        return data
    
    @staticmethod
    def invalidate_client_cache(client_id):
        """Invalidate cache for specific client"""
        cache_keys = [
            f'client_stats_{client_id}',
            f'client_interactions_{client_id}',
            f'client_analytics_{client_id}'
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def invalidate_analytics_cache():
        """Invalidate all analytics cache"""
        cache_keys = [
            'crm_acquisition_data',
            'crm_status_distribution', 
            'crm_type_distribution',
            'crm_regional_distribution',
            'crm_interaction_trends',
            'crm_performance_metrics'
        ]
        cache.delete_many(cache_keys)


class CRMNotificationUtils:
    """Utilities for CRM notifications"""
    
    @staticmethod
    def notify_team_of_new_client(client, created_by):
        """Notify team when new client is added"""
        from core.models import UserProfile
        
        # Notify managers and assigned team members
        managers = User.objects.filter(
            profile__user_type__in=['blitzhub_admin', 'it_admin'],
            is_active=True
        )
        
        for manager in managers:
            if manager != created_by:
                create_notification(
                    user=manager,
                    title="New Client Added",
                    message=f"New client '{client.name}' added by {created_by.get_full_name()}",
                    notification_type="info"
                )
    
    @staticmethod
    def notify_of_high_value_interaction(interaction):
        """Notify managers of high-value interactions"""
        # Define high-value criteria
        if (interaction.client.total_value > 10000 or 
            interaction.client.priority == 'vip' or
            interaction.outcome == 'positive'):
            
            managers = User.objects.filter(
                profile__user_type__in=['blitzhub_admin'],
                is_active=True
            )
            
            for manager in managers:
                create_notification(
                    user=manager,
                    title="High-Value Client Interaction",
                    message=f"Important interaction with {interaction.client.name}",
                    notification_type="success"
                )
    
    @staticmethod
    def send_daily_followup_reminders():
        """Send daily follow-up reminders to team"""
        from .models import CustomerInteraction
        
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        # Get follow-ups due today and tomorrow
        due_today = CustomerInteraction.objects.filter(
            next_followup__date=today
        ).select_related('client', 'created_by')
        
        due_tomorrow = CustomerInteraction.objects.filter(
            next_followup__date=tomorrow
        ).select_related('client', 'created_by')
        
        # Group by user
        user_reminders = {}
        
        for interaction in due_today:
            if interaction.created_by:
                if interaction.created_by not in user_reminders:
                    user_reminders[interaction.created_by] = {'today': [], 'tomorrow': []}
                user_reminders[interaction.created_by]['today'].append(interaction)
        
        for interaction in due_tomorrow:
            if interaction.created_by:
                if interaction.created_by not in user_reminders:
                    user_reminders[interaction.created_by] = {'today': [], 'tomorrow': []}
                user_reminders[interaction.created_by]['tomorrow'].append(interaction)
        
        # Send notifications
        for user, reminders in user_reminders.items():
            today_count = len(reminders['today'])
            tomorrow_count = len(reminders['tomorrow'])
            
            if today_count > 0 or tomorrow_count > 0:
                message = []
                if today_count > 0:
                    message.append(f"{today_count} follow-up{'s' if today_count > 1 else ''} due today")
                if tomorrow_count > 0:
                    message.append(f"{tomorrow_count} follow-up{'s' if tomorrow_count > 1 else ''} due tomorrow")
                
                create_notification(
                    user=user,
                    title="Follow-up Reminders",
                    message=", ".join(message),
                    notification_type="info"
                )


def get_crm_dashboard_data(user):
    """Get dashboard data for CRM"""
    from .models import Client, CustomerInteraction
    
    # Check user permissions
    from core.utils import check_app_permission
    if not check_app_permission(user, 'crm', 'view'):
        return {}
    
    # Get basic stats
    total_clients = Client.objects.count()
    active_clients = Client.objects.filter(status__in=['prospect', 'client']).count()
    leads = Client.objects.filter(status='lead').count()
    
    # Get recent activity
    recent_clients = Client.objects.order_by('-created_at')[:5]
    recent_interactions = CustomerInteraction.objects.select_related(
        'client'
    ).order_by('-created_at')[:5]
    
    # Get upcoming follow-ups
    upcoming_followups = CustomerInteraction.objects.filter(
        next_followup__isnull=False,
        next_followup__gte=timezone.now(),
        next_followup__lte=timezone.now() + timedelta(days=7)
    ).select_related('client').order_by('next_followup')[:5]
    
    # Get overdue follow-ups
    overdue_followups = CustomerInteraction.objects.filter(
        next_followup__isnull=False,
        next_followup__lt=timezone.now()
    ).select_related('client').order_by('next_followup')[:5]
    
    return {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'leads': leads,
        'recent_clients': recent_clients,
        'recent_interactions': recent_interactions,
        'upcoming_followups': upcoming_followups,
        'overdue_followups': overdue_followups,
    }


def run_daily_crm_tasks():
    """Run daily CRM maintenance tasks"""
    logger.info("Starting daily CRM tasks...")
    
    # Update lead scores
    updated_scores = CRMAutomation.update_lead_scores()
    logger.info(f"Updated lead scores for {updated_scores} clients")
    
    # Check overdue follow-ups
    overdue_count = CRMAutomation.check_overdue_followups()
    logger.info(f"Found {overdue_count} overdue follow-ups")
    
    # Auto-assign leads
    assigned_count = CRMAutomation.auto_assign_leads()
    logger.info(f"Auto-assigned {assigned_count} leads")
    
    # Send daily reminders
    CRMNotificationUtils.send_daily_followup_reminders()
    logger.info("Sent daily follow-up reminders")
    
    # Invalidate analytics cache to refresh data
    CRMCacheUtils.invalidate_analytics_cache()
    logger.info("Refreshed analytics cache")
    
    logger.info("Daily CRM tasks completed successfully")


def setup_crm_permissions():
    """Setup default CRM permissions for user types"""
    from core.models import AppPermission, UserProfile
    
    # Setup default permissions based on user types
    permission_mapping = {
        'blitzhub_admin': 'admin',
        'it_admin': 'admin', 
        'employee': 'edit',  # Can be customized per employee
    }
    
    for user_profile in UserProfile.objects.filter(user_type__in=permission_mapping.keys()):
        permission_level = permission_mapping[user_profile.user_type]
        
        AppPermission.objects.get_or_create(
            user=user_profile.user,
            app='crm',
            defaults={'permission_level': permission_level}
        )
    
    logger.info("CRM permissions setup completed")
