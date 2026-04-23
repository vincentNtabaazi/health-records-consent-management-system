from django.utils import timezone
from django.db import models
from users.models import User
from patients.models import MedicalRecord
from users.models import User, Role

# Create your models here.
class Consent(models.Model):
    CONSENT_TYPE_CHOICES = [
        ('explicit', 'Explicit Consent'),
        ('implied', 'Implied Consent'),  # Though generally not recommended for sensitive data
        ('opt-in', 'Opt-in Consent'),
        ('opt-out', 'Opt-out Consent'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
        ('denied', 'Denied'),
    ]

    POLICY_EVALUATION_CHOICES = [
        ('compliant', 'Compliant'),
        ('non-compliant', 'Non-Compliant'),
        ('n/a', 'Not Applicable'),  # If policy evaluation hasn't run yet
    ]

    consent_id = models.CharField(max_length=100, unique=True, editable=False,
                                  help_text="Unique identifier for the consent record.")

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consents_as_patient',
                                help_text="The patient or data subject providing consent.")

    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    data_category = models.CharField(
        max_length=100,
        choices=MedicalRecord.DATA_CATEGORY_CHOICES
    )

    purpose = models.TextField(help_text="The specific purpose for which the data is being collected and processed.")

    consent_type = models.CharField(max_length=50, choices=CONSENT_TYPE_CHOICES, default='explicit',
                                    help_text="The mechanism by which consent was obtained.")

    policy_evaluation_result = models.CharField(max_length=50, choices=POLICY_EVALUATION_CHOICES, default='n/a',
                                                help_text="Result of the policy compliance evaluation.")

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending',
                              help_text="Current status of the consent (e.g., active, withdrawn, expired).")

    created_date = models.DateTimeField(auto_now_add=True,
                                        help_text="Date and time when the consent record was created.")

    decision_date = models.DateTimeField(null=True, blank=True,
                                         help_text="Date and time when the patient made a decision (e.g., granted, withdrew).")

    expiry_date = models.DateTimeField(null=True, blank=True,
                                       help_text="Date and time when the consent automatically expires.")

    # Optional field for additional notes or details about the consent
    notes = models.TextField(blank=True, help_text="Additional notes or details about the consent.")

    class Meta:
        verbose_name = "Patient Consent"
        verbose_name_plural = "Patient Consents"
        ordering = ['-created_date']
        # You might want to add a unique_together constraint if a patient can only give one type of consent for a specific purpose to a specific processor
        # unique_together = ('patient', 'data_processor', 'data_type', 'purpose')

    def __str__(self):
        return f"Consent ID: {self.consent_id} - Patient: {self.patient.username} - Data Category: {self.data_category}"

    def save(self, *args, **kwargs):
        if not self.created_date:
            self.created_date = timezone.now()

        if not self.consent_id:
            # Generate a simple consent ID. For production, consider a more robust UUID or hash.
            self.consent_id = f"CONSENT-{self.patient.id}-{self.role.id}-{self.created_date.strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)

    def withdraw_consent(self):
        """Action to withdraw consent."""
        if self.status == 'active':
            self.status = 'withdrawn'
            self.decision_date = timezone.now()
            self.save()
            return True
        return False