from django.utils import timezone

from patients.models import ConsentPolicy
from users.models import RolePermission
from services.odrl import evaluate_odrl_payload



def permission_codename(action: str, category: str) -> str:
    return f"can_{action}_{category}_records"



def check_access(user, medical_record, action, purpose=None):
    """
    Final decision = base role permission + active consent policy + ODRL constraint evaluation.
    """
    if not user.is_authenticated:
        return False

    if hasattr(medical_record.patient, "user") and medical_record.patient.user_id == user.id:
        return True

    role = getattr(user, "role", None)
    if not role:
        return False

    permission_name = permission_codename(action, medical_record.data_category)

    role_allows_action = RolePermission.objects.filter(
        role=role,
        permission__name=permission_name,
    ).exists()
    if not role_allows_action:
        return False

    today = timezone.now().date()
    policies = (
        ConsentPolicy.objects
        .select_related("source_consent", "permission")
        .filter(
            patient=medical_record.patient,
            role=role,
            permission__name=permission_name,
            data_category=medical_record.data_category,
            active=True,
        )
    )

    for policy in policies:
        if policy.expiry_date and policy.expiry_date < today:
            continue
        if purpose and policy.purpose and policy.purpose != purpose:
            continue

        payload = {}
        if policy.source_consent:
            payload = policy.source_consent.odrl_policy

        if evaluate_odrl_payload(
            payload,
            action=action,
            category=medical_record.data_category,
            purpose=purpose or policy.purpose,
            assignee_id=user.id,
            when_date=today,
        ):
            return True

    return False
