from patients.models import ConsentPolicy
from users.models import RolePermission


def check_access(user, medical_record, action):
    role = user.role

    # Step 1: Check role permission
    permission_allowed = RolePermission.objects.filter(
        role=role,
        permission__name=action
    ).exists()

    if not permission_allowed:
        return False

    # Step 2: Check consent policy
    consent = ConsentPolicy.objects.filter(
        patient=medical_record.patient,
        role=role,
        permission__name=action,
        data_category=medical_record.data_category,
        active=True
    ).exists()

    return consent