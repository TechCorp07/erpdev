# core/management/commands/create_test_users.py
from django.conf import settings
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile, ApprovalRequest
from django.db import transaction
import logging

logger = logging.getLogger('core.management')

class Command(BaseCommand):
    help = 'Create test users for development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of test users to create (default: 10)'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['customer', 'blogger', 'employee'],
            default='customer',
            help='Type of test users to create'
        )

    def handle(self, *args, **options):
        count = options['count']
        user_type = options['type']
        
        if not settings.DEBUG:
            self.stdout.write(
                self.style.ERROR("This command can only be run in DEBUG mode")
            )
            return
        
        created_users = []
        
        try:
            with transaction.atomic():
                for i in range(count):
                    username = f"test_{user_type}_{i+1:03d}"
                    email = f"{username}@test.blitztechelectronics.co.zw"
                    
                    # Check if user already exists
                    if User.objects.filter(username=username).exists():
                        self.stdout.write(f"User {username} already exists, skipping")
                        continue
                    
                    # Create user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password='TestPassword123!',
                        first_name=f"Test",
                        last_name=f"{user_type.title()}{i+1:03d}"
                    )
                    
                    # Update profile
                    profile = user.profile
                    profile.user_type = user_type
                    profile.phone = f"+263{77}{1000000 + i:07d}"
                    profile.address = f"{i+1} Test Street, Harare, Zimbabwe"
                    profile.billing_address = profile.address
                    profile.profile_completed = True
                    
                    if user_type == 'customer':
                        profile.shop_approved = True
                        profile.crm_approved = False
                    elif user_type == 'blogger':
                        profile.shop_approved = True
                        profile.crm_approved = False
                        profile.blog_approved = False
                    
                    profile.save()
                    
                    # Create approval requests for non-employees
                    if user_type in ['customer', 'blogger']:
                        ApprovalRequest.objects.create(
                            user=user,
                            request_type='crm',
                            status='pending',
                            requested_reason=f"Test {user_type} requesting CRM access for development/testing",
                            business_justification=f"Test user for {user_type} workflow testing"
                        )
                        
                        if user_type == 'blogger':
                            ApprovalRequest.objects.create(
                                user=user,
                                request_type='blog',
                                status='pending',
                                requested_reason="Test blogger requesting blog management access",
                                business_justification="Test user for blogger workflow testing"
                            )
                    
                    created_users.append(username)
                    self.stdout.write(f"Created test user: {username}")
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nSuccessfully created {len(created_users)} test {user_type} users"
                    )
                )
                
                if created_users:
                    self.stdout.write("\nTest credentials:")
                    self.stdout.write("Username: test_<type>_001, test_<type>_002, etc.")
                    self.stdout.write("Password: TestPassword123!")
                    self.stdout.write("Email: <username>@test.blitztechelectronics.co.zw")
                
                logger.info(f"Created {len(created_users)} test {user_type} users")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error creating test users: {str(e)}")
            )
            logger.error(f"Error creating test users: {str(e)}")
