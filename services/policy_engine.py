# services/policy_engine.py

from django.utils import timezone
from patients.models import ConsentPolicy
from users.models import RolePermission
from services.odrl import evaluate_odrl_payload


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def permission_codename(action: str, category: str) -> str:
    return f"can_{action}_{category}_records"


# --------------------------------------------------------------------------
# Original check_access (unchanged - written by teammate)
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Decision constants
# --------------------------------------------------------------------------

DECISION_ALLOW          = 'allow'
DECISION_DENY           = 'deny'
DECISION_ALLOW_REDACTED = 'limited'


# --------------------------------------------------------------------------
# Core governance rules
# --------------------------------------------------------------------------

def _apply_governance_rules(requester, patient, resource_type, purpose):
    """
    Evaluate governance rules in priority order.

    Returns (decision, reason, matched_consent)

    Rule priority:
        1. purpose missing                        -> DENY
        2. no matching consent found              -> DENY
           (checks data_type + purpose + active;
            researcher: any active consent is sufficient)
        3. consent withdrawn                      -> DENY
        4. consent expired                        -> DENY
        5. consent not active                     -> DENY
        6. role has no permission                 -> DENY
        7. researcher role                        -> ALLOW_WITH_REDACTION
        8. processor role + treatment purpose     -> ALLOW (full)
        9. all other valid cases                  -> ALLOW
    """
    from consents.models import Consent

    # Rule 1: purpose must be provided
    if not purpose or purpose.strip() == '':
        return DECISION_DENY, 'Request denied: purpose field is empty.', None

    # Resolve role once
    role = getattr(requester, 'role', None)
    role_name = role.name if role else None

    # Rule 2: consent existence check
    # Researcher: any active consent from the patient is sufficient (anonymised access)
    # All other roles: consent must match data_type and purpose
    if role_name == 'researcher':
        consent = Consent.objects.filter(
            patient=patient.user,
            status='active',
        ).order_by('-created_date').first()
    else:
        consent = Consent.objects.filter(
            patient=patient.user,
            data_processor=requester,
            data_type__contains=[resource_type],
            purpose=purpose,
            status='active',
        ).order_by('-created_date').first()

    if not consent:
        return (
            DECISION_DENY,
            (
                f'Request denied: no active consent found for patient covering '
                f'resource_type="{resource_type}" and purpose="{purpose}".'
            ),
            None,
        )

    # Rule 3: consent withdrawn (defence-in-depth, status filter above should catch this)
    if consent.status == 'withdrawn':
        return (
            DECISION_DENY,
            f'Request denied: consent {consent.consent_id} has been withdrawn.',
            consent,
        )

    # Rule 4: consent expired
    today = timezone.now().date()
    if consent.expiry_date and consent.expiry_date < today:
        return (
            DECISION_DENY,
            f'Request denied: consent {consent.consent_id} expired on {consent.expiry_date}.',
            consent,
        )

    # Rule 5: consent not active (catches 'pending', 'denied', etc.)
    if consent.status != 'active':
        return (
            DECISION_DENY,
            f'Request denied: consent {consent.consent_id} status is "{consent.status}".',
            consent,
        )

    # Rule 6: role must have the relevant RolePermission
    if not role:
        return DECISION_DENY, 'Request denied: requester has no assigned role.', consent

    has_permission = RolePermission.objects.filter(
        role=role,
        permission__name=permission_codename('read', resource_type),
    ).exists()

    if not has_permission:
        return (
            DECISION_DENY,
            (
                f'Request denied: role "{role_name}" does not have permission '
                f'to read "{resource_type}".'
            ),
            consent,
        )

    # Rule 7: researcher -> redacted/anonymised access only
    if role_name == 'researcher':
        return (
            DECISION_ALLOW_REDACTED,
            (
                f'Access granted with redaction: researcher role may only receive '
                f'anonymised "{resource_type}" data for purpose "{purpose}".'
            ),
            consent,
        )

    # Rule 8: processor (doctor) + treatment purpose -> full access
    if role_name == 'processor' and purpose == 'treatment':
        return (
            DECISION_ALLOW,
            (
                f'Full access granted: processor role with treatment purpose '
                f'matched consent {consent.consent_id}.'
            ),
            consent,
        )

    # Rule 9: all other valid cases
    return (
        DECISION_ALLOW,
        (
            f'Access granted: active consent {consent.consent_id} covers '
            f'role "{role_name}" for purpose "{purpose}".'
        ),
        consent,
    )


# --------------------------------------------------------------------------
# Public API: evaluate_access
# --------------------------------------------------------------------------

def evaluate_access(requester, patient, resource_type, purpose, action='read'):
    """
    Main entry point for access control.
    Creates an AccessRequest, applies governance rules, writes a DecisionLog.
    Returns: DecisionLog instance
    """
    from services.audit_logger import create_access_request, write_decision_log

    access_request = create_access_request(
        requester, patient, resource_type, purpose, action
    )

    decision, reason, matched_consent = _apply_governance_rules(
        requester, patient, resource_type, purpose
    )

    log = write_decision_log(access_request, decision, reason, matched_consent)

    return log


# --------------------------------------------------------------------------
# Public API: check_compliance
# --------------------------------------------------------------------------

def check_compliance(patient):
    """
    Wrapper around check_violations for backwards compatibility.
    """
    from services.compliance_checker import check_violations
    return check_violations(patient)


def data_anonymity(patient):

    return None