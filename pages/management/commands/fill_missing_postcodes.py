import random
import string

from django.core.management.base import BaseCommand
from users.models import User


def generate_uk_postcode():

    area = ''.join(
        random.choices(
            string.ascii_uppercase,
            k=random.choice([1, 2])
        )
    )

    district = str(random.randint(1, 99))

    optional_letter = random.choice([
        '',
        random.choice(string.ascii_uppercase)
    ])

    sector = str(random.randint(0, 9))

    unit = ''.join(
        random.choices(
            string.ascii_uppercase,
            k=2
        )
    )

    return f"{area}{district}{optional_letter} {sector}{unit}"


class Command(BaseCommand):

    help = "Fill missing postal codes for users"

    def handle(self, *args, **kwargs):

        users = User.objects.filter(
            postal_code__isnull=True
        ) | User.objects.filter(
            postal_code=''
        )

        updated = 0

        for user in users:

            user.postal_code = generate_uk_postcode()
            user.save()

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {updated} users with postal codes."
            )
        )