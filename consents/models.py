from django.db import models, transaction
from django.utils import timezone

from patients.models import Patient, ConsentPolicy
from users.models import User, CustomPermission
from services.odrl import (
    build_odrl_denial_policy,
    build_odrl_privacy_policy,
    build_odrl_request_policy,
    infer_data_category_from_permission,
    pretty_json,
)


class Consent(models.Model):
    CONSENT_TYPE_MANUAL_REVIEW = 'explicit'
    CONSENT_TYPE_SUBJECT_PREFERENCE = 'implied'
    CONSENT_TYPE_PARTIAL_APPROVAL = 'opt-in'
    CONSENT_TYPE_WITHDRAWN = 'opt-out'

    CONSENT_TYPE_CHOICES = [
        (CONSENT_TYPE_MANUAL_REVIEW, 'Manual Review'),
        (CONSENT_TYPE_SUBJECT_PREFERENCE, 'Subject Preference Auto-Approval'),
        (CONSENT_TYPE_PARTIAL_APPROVAL, 'Partial Approval'),
        (CONSENT_TYPE_WITHDRAWN, 'Withdrawn / Revoked'),
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
        ('n/a', 'Not Applicable'),
    ]

    consent_id = models.CharField(max_length=100, unique=True, editable=False)
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consents_as_patient')
    data_processor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consents_processed')
    data_type = models.CharField(max_length=255, blank=True)
    purpose = models.TextField()
    consent_type = models.CharField(max_length=50, choices=CONSENT_TYPE_CHOICES, default=CONSENT_TYPE_MANUAL_REVIEW)
    policy_evaluation_result = models.CharField(max_length=50, choices=POLICY_EVALUATION_CHOICES, default='n/a')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    created_date = models.DateTimeField(auto_now_add=True)
    decision_date = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    requested_permissions = models.JSONField(default=list, blank=True)
    granted_permissions = models.JSONField(default=list, blank=True)
    odrl_request = models.JSONField(default=dict, blank=True)
    odrl_policy = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Patient Consent'
        verbose_name_plural = 'Patient Consents'
        ordering = ['-created_date']

    def __str__(self):
        return f"{self.consent_id} | {self.patient.username} -> {self.data_processor.username} | {self.status}"

    def save(self, *args, **kwargs):
        if not self.consent_id:
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            self.consent_id = f"CONSENT-{self.patient_id}-{self.data_processor_id}-{timestamp}"
        super().save(*args, **kwargs)

    @property
    def requested_permission_objects(self):
        return list(CustomPermission.objects.filter(id__in=self.requested_permissions).order_by('name'))

    @property
    def granted_permission_objects(self):
        return list(CustomPermission.objects.filter(name__in=self.granted_permissions).order_by('name'))

    @property
    def odrl_policy_pretty(self):
        return pretty_json(self.odrl_policy or self.odrl_request)

    def build_request_policy(self):
        permissions = self.requested_permission_objects
        self.odrl_request = build_odrl_request_policy(self, permissions)
        return self.odrl_request

    @transaction.atomic
    def approve(self, granted_permission_ids=None, approval_path=None):
        patient_profile = Patient.objects.get(user=self.patient)
        requested_permissions = list(CustomPermission.objects.filter(id__in=self.requested_permissions))
        requested_permission_ids = {permission.id for permission in requested_permissions}

        if granted_permission_ids is None:
            approved_permission_ids = requested_permission_ids
        else:
            approved_permission_ids = {int(item) for item in granted_permission_ids if int(item) in requested_permission_ids}

        approved_permissions = list(CustomPermission.objects.filter(id__in=approved_permission_ids))

        ConsentPolicy.objects.filter(source_consent=self).update(active=False)
        created_policy_names = []

        for permission in approved_permissions:
            category = infer_data_category_from_permission(permission.name)
            consent_policy, _ = ConsentPolicy.objects.update_or_create(
                patient=patient_profile,
                role=self.data_processor.role,
                permission=permission,
                data_category=category,
                source_consent=self,
                defaults={
                    'purpose': self.purpose,
                    'expiry_date': self.expiry_date,
                    'active': True,
                    'odrl_rule_uid': f"urn:consent-rule:{self.consent_id}:{permission.id}",
                }
            )
            created_policy_names.append(consent_policy.permission.name)

        if created_policy_names:
            self.granted_permissions = sorted(created_policy_names)
            self.policy_evaluation_result = 'compliant'
            self.status = 'active'
            self.decision_date = timezone.now()
            self.odrl_policy = build_odrl_privacy_policy(self, approved_permissions)
            if approval_path:
                self.consent_type = approval_path
        else:
            self.granted_permissions = []
            self.policy_evaluation_result = 'non-compliant'
            self.status = 'denied'
            self.decision_date = timezone.now()
            self.odrl_policy = build_odrl_denial_policy(self, requested_permissions)
            if approval_path:
                self.consent_type = approval_path

        self.save(update_fields=[
            'granted_permissions',
            'policy_evaluation_result',
            'status',
            'decision_date',
            'odrl_policy',
            'consent_type',
        ])
        return self

    @transaction.atomic
    def reject(self, approval_path=None):
        permissions = self.requested_permission_objects
        ConsentPolicy.objects.filter(source_consent=self).update(active=False)
        self.granted_permissions = []
        self.policy_evaluation_result = 'non-compliant'
        self.status = 'denied'
        self.decision_date = timezone.now()
        self.odrl_policy = build_odrl_denial_policy(self, permissions)
        if approval_path:
            self.consent_type = approval_path
        self.save(update_fields=[
            'granted_permissions',
            'policy_evaluation_result',
            'status',
            'decision_date',
            'odrl_policy',
            'consent_type',
        ])
        return self

    @transaction.atomic
    def withdraw_consent(self):
        if self.status != 'active':
            return False

        ConsentPolicy.objects.filter(source_consent=self, active=True).update(active=False)
        self.status = 'withdrawn'
        self.consent_type = self.CONSENT_TYPE_WITHDRAWN
        self.decision_date = timezone.now()
        current_policy = dict(self.odrl_policy or {})
        current_policy['status'] = 'withdrawn'
        current_policy['revokedAt'] = timezone.now().isoformat()
        self.odrl_policy = current_policy
        self.save(update_fields=['status', 'consent_type', 'decision_date', 'odrl_policy'])
        return True




class AccessRequest(models.Model):
    ACTION_CHOICES = [
        ('read','Read'),('write','Write'),('share','Share'),('delete','Delete'),
    ]
    PURPOSE_CHOICES = [
        ('treatment','Treatment'),('research','Research'),
        ('audit','Audit'),('emergency','Emergency'),('insurance','Insurance'),
    ]
    STATUS_CHOICES = [
        ('pending','Pending'),('evaluated','Evaluated'),
    ]

    requester     = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='access_requests'
    )
    patient       = models.ForeignKey(
        'patients.Patient', on_delete=models.CASCADE, related_name='access_requests'
    )
    resource_type = models.CharField(max_length=100)
    purpose       = models.CharField(max_length=50, choices=PURPOSE_CHOICES)
    action        = models.CharField(max_length=20, choices=ACTION_CHOICES, default='read')
    requested_at  = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Request#{self.id} by {self.requester.username}: {self.action} {self.resource_type}"


class DecisionLog(models.Model):
    DECISION_CHOICES = [
        ('allow','Allow'),('deny','Deny'),('limited','Limited'),
    ]
    COMPLIANCE_CHOICES = [
        ('compliant','Compliant'),('non_compliant','Non-Compliant'),('warning','Warning'),
    ]

    access_request    = models.OneToOneField(
        AccessRequest, on_delete=models.CASCADE, related_name='decision'
    )
    decision          = models.CharField(max_length=20, choices=DECISION_CHOICES)
    reason            = models.TextField()
    matched_consent   = models.ForeignKey(
        Consent, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions'
    )
    checked_at        = models.DateTimeField(auto_now_add=True)
    compliance_status = models.CharField(
        max_length=20, choices=COMPLIANCE_CHOICES, default='compliant'
    )

    def __str__(self):
        return f"Decision#{self.id} → {self.decision} ({self.compliance_status})"