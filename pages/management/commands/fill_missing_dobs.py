import random
from datetime import date
from django.core.management.base import BaseCommand
from users.models import User


def generate_random_dob():

    year = random.randint(1970, 2020)

    month = random.randint(1, 12)

    if month == 2:
        day = random.randint(1, 28)

    elif month in [4, 6, 9, 11]:
        day = random.randint(1, 30)

    else:
        day = random.randint(1, 31)

    return date(year, month, day)


class Command(BaseCommand):

    help = "Fill missing dates of birth for users"

    def handle(self, *args, **kwargs):

        users = User.objects.filter(
            date_of_birth__isnull=True
        )

        updated = 0

        for user in users:

            user.date_of_birth = generate_random_dob()
            user.save()

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} users with dates of birth."
            )
        )