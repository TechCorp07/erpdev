# core/management/commands/list_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import EmployeeRole, AppPermission
from core.utils import get_user_roles, get_user_permissions

class Command(BaseCommand):
    help = 'List roles and permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Show permissions for specific user',
        )
        parser.add_argument(
            '--role',
            type=str,
            help='Show permissions for specific role',
        )

    def handle(self, *args, **options):
        if options['user']:
            self.show_user_permissions(options['user'])
        elif options['role']:
            self.show_role_permissions(options['role'])
        else:
            self.show_all_roles_and_permissions()

    def show_user_permissions(self, username):
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User {username} does not exist')
            )
            return

        self.stdout.write(f'\nPermissions for user: {username}')
        self.stdout.write('=' * 50)

        # Show user type
        if hasattr(user, 'profile'):
            self.stdout.write(f'User Type: {user.profile.get_user_type_display()}')

        # Show roles
        roles = get_user_roles(user)
        if roles:
            self.stdout.write(f'Roles: {", ".join(roles)}')
        else:
            self.stdout.write('Roles: None')

        # Show permissions
        permissions = get_user_permissions(user)
        if permissions:
            self.stdout.write('\nApp Permissions:')
            for app, level in permissions.items():
                self.stdout.write(f'  {app}: {level}')
        else:
            self.stdout.write('\nApp Permissions: None')

    def show_role_permissions(self, role_name):
        try:
            role = EmployeeRole.objects.get(name=role_name)
        except EmployeeRole.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Role {role_name} does not exist')
            )
            return

        self.stdout.write(f'\nPermissions for role: {role.display_name}')
        self.stdout.write('=' * 50)

        permissions = AppPermission.objects.filter(role=role)
        if permissions:
            for perm in permissions:
                self.stdout.write(f'{perm.get_app_display()}: {perm.get_permission_level_display()}')
        else:
            self.stdout.write('No permissions assigned')

    def show_all_roles_and_permissions(self):
        self.stdout.write('\nAll Roles and Permissions')
        self.stdout.write('=' * 50)

        for role in EmployeeRole.objects.all():
            self.stdout.write(f'\n{role.display_name} ({role.name})')
            self.stdout.write(f'  Hierarchy: {role.get_hierarchy_level_display()}')
            self.stdout.write(f'  Requires GM Approval: {role.requires_gm_approval}')
            self.stdout.write(f'  Can Assign Roles: {role.can_assign_roles}')

            permissions = AppPermission.objects.filter(role=role)
            if permissions:
                self.stdout.write('  Permissions:')
                for perm in permissions:
                    self.stdout.write(f'    {perm.get_app_display()}: {perm.get_permission_level_display()}')
            else:
                self.stdout.write('  Permissions: None')

