from django.db import models
from users.models import User, Role, CustomPermission, RolePermission


# Create your models here.
class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name


class MedicalRecord(models.Model):

    DATA_CATEGORY_CHOICES = [
        ('diagnosis', 'Diagnosis'),
        ('treatment', 'Treatment'),
        ('mental_health', 'Mental Health'),
        ('billing', 'Billing'),
        ('lab_results', 'Lab Results'),
        ('medication', 'Medication'),
        ('allergies', 'Allergies'),
        ('immunization', 'Immunization'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    data_category = models.CharField(
        max_length=100,
        choices=DATA_CATEGORY_CHOICES,
        default='diagnosis',
        help_text="Select the category of the medical record data."
    )
    created_at = models.DateTimeField(auto_now_add=True)


class ConsentPolicy(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(CustomPermission, on_delete=models.CASCADE)
    data_category = models.CharField(max_length=100)
    expiry_date = models.DateField()
    active = models.BooleanField(default=True)


class PatientPermission(models.Model):
    """Links a RolePermission specifically to a Patient if needed"""
    role_permission = models.ForeignKey(RolePermission, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)