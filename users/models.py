from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

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

class User(AbstractUser):

    role = models.ForeignKey("Role", on_delete=models.SET_NULL, null=True, blank=True, default=None)

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

    @property
    def active_consents(self):
        return self.consents_as_patient.filter(status='active').count()
