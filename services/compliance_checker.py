from django.utils import timezone
from datetime import timedelta
from services.audit_logger import get_audit_trail

DECISION_ALLOW          = 'allow'
DECISION_DENY           = 'deny'
DECISION_ALLOW_REDACTED = 'limited'


def check_violations(patient):
    """
    Scan audit trail for a patient and detect compliance violations.

    Violation types:
        POST_WITHDRAWAL_ACCESS   - access allowed after consent was withdrawn
        RESEARCHER_FULL_ACCESS   - researcher got full access instead of redacted
        EMPTY_PURPOSE_ALLOWED    - request with no purpose was not denied
        ALLOW_WITHOUT_CONSENT    - allow decision has no matched consent record
    """
    logs = get_audit_trail(patient)
    violations = []

    for log in logs:
        req  = log.access_request
        role = getattr(req.requester, 'role', None)

        # Check 1: access after consent withdrawal
        if (log.matched_consent
                and log.matched_consent.status == 'withdrawn'
                and log.decision == DECISION_ALLOW):
            violations.append({
                'type':      'POST_WITHDRAWAL_ACCESS',
                'severity':  'HIGH',
                'requester': req.requester.username,
                'resource':  req.resource_type,
                'purpose':   req.purpose,
                'time':      log.checked_at,
                'detail':    (
                    f'Access allowed after consent '
                    f'{log.matched_consent.consent_id} was withdrawn.'
                ),
            })

        # Check 2: researcher received full access
        if (role and role.name == 'researcher'
                and log.decision == DECISION_ALLOW):
            violations.append({
                'type':      'RESEARCHER_FULL_ACCESS',
                'severity':  'HIGH',
                'requester': req.requester.username,
                'resource':  req.resource_type,
                'purpose':   req.purpose,
                'time':      log.checked_at,
                'detail':    (
                    'Researcher was granted full access; '
                    'should have been redacted.'
                ),
            })

        # Check 3: empty purpose was not denied
        if (not req.purpose or req.purpose.strip() == ''):
            if log.decision != DECISION_DENY:
                violations.append({
                    'type':      'EMPTY_PURPOSE_ALLOWED',
                    'severity':  'MEDIUM',
                    'requester': req.requester.username,
                    'resource':  req.resource_type,
                    'purpose':   '(empty)',
                    'time':      log.checked_at,
                    'detail':    (
                        'Request with no stated purpose was not denied.'
                    ),
                })

        # Check 4: allow with no matched consent
        if (log.decision == DECISION_ALLOW
                and log.matched_consent is None):
            violations.append({
                'type':      'ALLOW_WITHOUT_CONSENT',
                'severity':  'HIGH',
                'requester': req.requester.username,
                'resource':  req.resource_type,
                'purpose':   req.purpose,
                'time':      log.checked_at,
                'detail':    (
                    'Access was allowed but no consent record was matched.'
                ),
            })

    all_logs    = logs
    allow_logs  = logs.filter(decision=DECISION_ALLOW)
    deny_logs   = logs.filter(decision=DECISION_DENY)
    redact_logs = logs.filter(decision=DECISION_ALLOW_REDACTED)
    total       = all_logs.count()

    return {
        'patient':         str(patient),
        'total_requests':  total,
        'allowed':         allow_logs.count(),
        'redacted':        redact_logs.count(),
        'denied':          deny_logs.count(),
        'compliance_rate': (
            round(
                (allow_logs.count() + redact_logs.count()) / total * 100, 1
            ) if total > 0 else 0
        ),
        'violation_count': len(violations),
        'violations':      violations,
    }


def get_expiring_consents_for_patient(patient_user, days_ahead=7):
    """
    Return active consents belonging to patient_user that expire
    within the next `days_ahead` days.
    Used to warn patients before their consent lapses.
    """
    from consents.models import Consent

    now    = timezone.now().date()
    cutoff = now + timedelta(days=days_ahead)

    return Consent.objects.filter(
        patient=patient_user,
        status='active',
        expiry_date__gte=now,
        expiry_date__lte=cutoff,
    ).select_related('data_processor').order_by('expiry_date')


def auto_expire_consents():
    """
    Automatically mark consents as 'expired' if their expiry_date
    has passed but their status is still 'active'.

    Enforces the Storage Limitation principle (GDPR Article 5(1)(e)).
    Returns the number of consents updated.
    """
    from consents.models import Consent

    today = timezone.now().date()

    expired_count = Consent.objects.filter(
        status='active',
        expiry_date__lt=today,
    ).update(status='expired')

    return expired_count