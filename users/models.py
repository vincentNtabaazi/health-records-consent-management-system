from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):

    ROLE_CHOICES = [
        ('subject', 'Data Subject'),
        ('processor', 'Data Processor'),
        ('regulator', 'Regulator'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    organization_name = models.CharField(max_length=255, blank=True, null=True)

    can_delegate = models.BooleanField(default=False)

    delegated_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)