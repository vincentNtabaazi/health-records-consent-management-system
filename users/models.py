from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from datetime import date

class Role(models.Model):

    ROLE_CHOICES = [
        ('subject', 'Data Subject'),
        ('processor', 'Data Processor'),
        ('regulator', 'Regulator'),
        ('researcher', 'Researcher'),
        ('insurance_agent', 'Insurance Agent'),
    ]
    name = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return self.name

class CustomPermission(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
    class Meta:
        verbose_name_plural = "Permissions"

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(CustomPermission, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.role.name} - {self.permission.name}"

uk_postcode_validator = RegexValidator(
    regex=r'^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$',
    message='Enter a valid UK postcode'
)

class User(AbstractUser):

    role = models.ForeignKey("Role", on_delete=models.SET_NULL, null=True, blank=True, default=None)

    organization_name = models.CharField(max_length=255, blank=True, null=True)

    can_delegate = models.BooleanField(default=False)

    postal_code = models.CharField(
        max_length=10,
        validators=[uk_postcode_validator],
        null=True,
        blank=True,
    )
    date_of_birth = models.DateField(blank=True, null=True)

    delegated_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def active_consents(self):
        return self.consents_as_patient.filter(status='active').count()

    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return (
                    today.year
                    - self.date_of_birth.year
                    - (
                            (today.month, today.day)
                            < (self.date_of_birth.month, self.date_of_birth.day)
                    )
            )
        return None

    def save(self, *args, **kwargs):
        if self.postal_code:
            self.postal_code = self.postal_code.upper().strip()
        super().save(*args, **kwargs)
