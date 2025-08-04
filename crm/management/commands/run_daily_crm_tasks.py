from django.core.management.base import BaseCommand
from crm.utils import run_daily_crm_tasks

class Command(BaseCommand):
    help = 'Run daily CRM maintenance tasks'
    
    def handle(self, *args, **options):
        self.stdout.write('Starting daily CRM tasks...')
        run_daily_crm_tasks()
        self.stdout.write(self.style.SUCCESS('Daily CRM tasks completed!'))
