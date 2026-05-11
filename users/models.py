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


class Delegation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('active', 'Active'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),
    ]

    data_subject = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='delegations'
    )
    proxy = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='delegated_as_proxy'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['data_subject'],
                condition=models.Q(status__in=['pending', 'accepted', 'active']),
                name='one_active_delegation_per_subject'
            )
        ]
        ordering = ['-created_at']


class DelegationLog(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('accepted', 'Accepted'),
        ('replaced', 'Replaced'),
        ('rejected', 'Rejected'),
        ('revoked', 'Revoked'),
        ('activation_requested', 'Activation Requested'),
    ]

    delegation = models.ForeignKey(
        Delegation,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='delegation_actions'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']
