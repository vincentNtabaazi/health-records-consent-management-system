# your_app/management/commands/generate_medical_permissions.py

from django.core.management.base import BaseCommand
from patients.models import MedicalRecord
from users.models import CustomPermission


class Command(BaseCommand):
    help = "Generate medical record permissions"

    def handle(self, *args, **kwargs):

        actions = ["create", "read", "edit", "delete"]

        permissions = []

        for value, display in MedicalRecord.DATA_CATEGORY_CHOICES:
            for action in actions:

                perm_name = f"can_{action}_{value}_records"

                # Avoid duplicates
                obj, created = CustomPermission.objects.get_or_create(
                    name=perm_name
                )

                if created:
                    permissions.append(perm_name)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done! {len(permissions)} permissions created."
            )
        )