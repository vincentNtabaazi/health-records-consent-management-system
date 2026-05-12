# your_app/management/commands/create_demo_users.py

import random
import string
from pathlib import Path

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password

from users.models import User, Role
from users.views import _create_patient
from django.conf import settings


class Command(BaseCommand):

    help = "Create demo users for the system"

    def generate_password(self, length=10):

        characters = (
            string.ascii_letters +
            string.digits
        )

        return ''.join(
            random.choice(characters)
            for _ in range(length)
        )

    def create_users_for_role(
        self,
        role_name,
        count,
        credentials
    ):

        try:
            role = Role.objects.get(name=role_name)

        except Role.DoesNotExist:

            self.stdout.write(
                self.style.ERROR(
                    f"Role '{role_name}' does not exist."
                )
            )

            return

        for i in range(1, count + 1):

            email = f"{role_name}{i}@example.com"

            if User.objects.filter(email=email).exists():

                self.stdout.write(
                    self.style.WARNING(
                        f"{email} already exists. Skipping."
                    )
                )

                continue

            password = self.generate_password()

            user = User(

                first_name=role_name.capitalize(),

                last_name=f"User{i}",

                email=email,

                organization_name=f"{role_name.capitalize()} Org",

                role=role,

                is_active=True,
            )

            if hasattr(User, "username"):

                user.username = email

            user.password = make_password(password)

            user.save()

            # Create patient profile for data subjects
            if role.name == "subject":

                try:
                    _create_patient(user)

                except Exception as e:

                    self.stdout.write(
                        self.style.WARNING(
                            f"Could not create patient "
                            f"for {email}: {e}"
                        )
                    )

            credentials.append({
                "email": email,
                "password": password,
                "role": role_name,
            })

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {email}"
                )
            )

    def handle(self, *args, **kwargs):

        credentials = []

        # Create users
        self.create_users_for_role(
            "regulator",
            2,
            credentials
        )

        self.create_users_for_role(
            "subject",
            10,
            credentials
        )

        self.create_users_for_role(
            "processor",
            2,
            credentials
        )

        # Save credentials file
        home = Path.home()

        file_path = (
                Path(settings.BASE_DIR)
                / "demo_user_credentials.txt"
        )

        with open(file_path, "w") as f:

            f.write("DEMO USER LOGIN DETAILS\n")
            f.write("=" * 50 + "\n\n")

            for cred in credentials:

                f.write(
                    f"Role: {cred['role']}\n"
                )

                f.write(
                    f"Email: {cred['email']}\n"
                )

                f.write(
                    f"Password: {cred['password']}\n"
                )

                f.write("\n")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCreated {len(credentials)} users."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Credentials saved to:\n{file_path}"
            )
        )