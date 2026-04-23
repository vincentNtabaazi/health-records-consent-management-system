from consents.models import AccessRequest, DecisionLog


def create_access_request(requester, patient, resource_type, purpose, action='read'):
    """
    Record an incoming access request before evaluation.
    """
    return AccessRequest.objects.create(
        requester=requester,
        patient=patient,
        resource_type=resource_type,
        purpose=purpose,
        action=action,
    )


def write_decision_log(access_request, decision, reason, matched_consent=None):
    """
    Write the outcome of a policy evaluation to DecisionLog.

    decision: 'allow' | 'deny' | 'limited'
    """
    if decision in ('allow', 'limited'):
        compliance = 'compliant'
    else:
        compliance = 'non_compliant'

    log = DecisionLog.objects.create(
        access_request=access_request,
        decision=decision,
        reason=reason,
        matched_consent=matched_consent,
        compliance_status=compliance,
    )

    access_request.status = 'evaluated'
    access_request.save()

    return log


def get_audit_trail(patient):
    """
    Return all audit records for a given patient, newest first.
    """
    return (
        DecisionLog.objects
        .filter(access_request__patient=patient)
        .select_related(
            'access_request',
            'access_request__requester',
            'access_request__requester__role',
            'matched_consent',
        )
        .order_by('-checked_at')
    )