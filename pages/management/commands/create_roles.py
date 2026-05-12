# your_app/management/commands/create_roles.py

from django.core.management.base import BaseCommand

from users.models import Role


class Command(BaseCommand):

    help = "Create system roles"

    def handle(self, *args, **kwargs):

        created_count = 0

        for value, display in Role.ROLE_CHOICES:

            role, created = Role.objects.get_or_create(
                name=value
            )

            if created:

                created_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created role: {value}"
                    )
                )

            else:

                self.stdout.write(
                    self.style.WARNING(
                        f"Role already exists: {value}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {created_count} new roles created."
            )
        )