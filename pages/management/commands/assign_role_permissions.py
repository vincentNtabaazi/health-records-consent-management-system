# your_app/management/commands/assign_role_permissions.py

from django.core.management.base import BaseCommand

from users.models import (
    Role,
    CustomPermission,
    RolePermission,
)


class Command(BaseCommand):

    help = "Assign permissions to system roles"

    ROLE_PERMISSION_RULES = {

        # Full access
        "regulator": [
            "create",
            "read",
            "edit",
            "delete",
        ],

        # Can mainly read/share data
        "processor": [
            "read",
        ],

        # Mostly read anonymized datasets
        "researcher": [
            "read",
        ],

        # Insurance can read limited info
        "insurance_agent": [
            "read",
        ],

        # Data subjects can view/edit their own
        "subject": [
            "read",
            "edit",
        ],
    }

    def handle(self, *args, **kwargs):

        assignments_created = 0

        for role_name, allowed_actions in (
            self.ROLE_PERMISSION_RULES.items()
        ):

            try:
                role = Role.objects.get(
                    name=role_name
                )

            except Role.DoesNotExist:

                self.stdout.write(
                    self.style.WARNING(
                        f"Role not found: {role_name}"
                    )
                )

                continue

            permissions = CustomPermission.objects.all()

            for permission in permissions:

                permission_name = permission.name

                # Example:
                # can_read_lab_results_records

                allowed = any(
                    f"can_{action}_" in permission_name
                    for action in allowed_actions
                )

                if allowed:

                    _, created = (
                        RolePermission.objects.get_or_create(
                            role=role,
                            permission=permission
                        )
                    )

                    if created:

                        assignments_created += 1

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Assigned "
                                f"{permission.name} "
                                f"to {role.name}"
                            )
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. "
                f"{assignments_created} "
                f"role-permission mappings created."
            )
        )