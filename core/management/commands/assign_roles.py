# core/management/commands/assign_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.utils import assign_role_to_user, get_user_roles
from core.models import EmployeeRole

class Command(BaseCommand):
    help = 'Assign roles to users'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to assign role to')
        parser.add_argument('role', type=str, help='Role name to assign')
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remove role instead of assigning',
        )

    def handle(self, *args, **options):
        username = options['username']
        role_name = options['role']
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User {username} does not exist')
            )
            return

        try:
            role = EmployeeRole.objects.get(name=role_name)
        except EmployeeRole.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Role {role_name} does not exist')
            )
            available_roles = EmployeeRole.objects.values_list('name', flat=True)
            self.stdout.write(f'Available roles: {", ".join(available_roles)}')
            return

        if options['remove']:
            from core.utils import remove_role_from_user
            success = remove_role_from_user(user, role_name)
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Removed role {role_name} from {username}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'User {username} did not have role {role_name}')
                )
        else:
            try:
                assign_role_to_user(user, role_name)
                self.stdout.write(
                    self.style.SUCCESS(f'Assigned role {role_name} to {username}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to assign role: {e}')
                )

        # Show current roles
        current_roles = get_user_roles(user)
        self.stdout.write(f'Current roles for {username}: {", ".join(current_roles)}')

