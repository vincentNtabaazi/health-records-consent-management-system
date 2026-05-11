from django.db.models.signals import post_init
from django.dispatch import receiver
from .models import User
import random
import string
from datetime import date
from django.db.models.signals import pre_save


def generate_uk_postcode():
    """
    Generates a random UK-style postcode.
    Example outputs:
    SO17 1BJ
    SW1A 1AA
    M1 1AE
    """

    area = ''.join(random.choices(string.ascii_uppercase, k=random.choice([1, 2])))

    district = str(random.randint(1, 99))

    optional_letter = random.choice(
        ['', random.choice(string.ascii_uppercase)]
    )

    sector = str(random.randint(0, 9))

    unit = ''.join(random.choices(string.ascii_uppercase, k=2))

    return f"{area}{district}{optional_letter} {sector}{unit}"


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


@receiver(pre_save, sender=User)
def fill_missing_user_fields(sender, instance, **kwargs):

    if not instance.postal_code:
        instance.postal_code = generate_uk_postcode()

    if not instance.date_of_birth:
        instance.date_of_birth = generate_random_dob()