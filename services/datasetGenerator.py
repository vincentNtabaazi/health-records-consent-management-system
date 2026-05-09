from django.db import models
from patients.models import PatientPermission, MedicalRecord
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from consents.models import Consent

def generate_dataset(role):
    now = timezone.now()

    consent_subquery = Consent.objects.filter(
        patient=OuterRef('patient__user'),
        role=role,
        data_category=OuterRef('data_category'),
        status='active'
    ).filter(
        models.Q(expiry_date__isnull=True) |
        models.Q(expiry_date__gt=now)
    ).values('expiry_date')[:1]

    return MedicalRecord.objects.annotate(
        consent_expiry=Subquery(consent_subquery)
    ).filter(
        consent_expiry__isnull=False
    )