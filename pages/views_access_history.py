from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.db.models import Count, Q

from consents.models import AccessRequest, DecisionLog


@login_required(login_url='users:login_view')
def access_history_view(request):
    from users.models import User
    from patients.models import Patient

    user_role = getattr(getattr(request.user, 'role', None), 'name', None)
    if user_role not in {'researcher', 'processor', 'insurance_agent'} and not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('You do not have permission to view this page.')

    # Get filter parameters
    patient_id = request.GET.get('patient_id', '')
    resource_type = request.GET.get('resource_type', '')
    purpose = request.GET.get('purpose', '')
    decision = request.GET.get('decision', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # Base queryset - user's own access requests
    history_qs = (
        DecisionLog.objects
        .select_related(
            'access_request',
            'access_request__requester',
            'access_request__patient',
            'access_request__patient__user',
            'matched_consent',
        )
        .filter(access_request__requester=request.user)
        .order_by('-checked_at')
    )

    # Apply filters
    if patient_id:
        history_qs = history_qs.filter(access_request__patient_id=patient_id)
    if resource_type:
        history_qs = history_qs.filter(access_request__resource_type=resource_type)
    if purpose:
        history_qs = history_qs.filter(access_request__purpose=purpose)
    if decision:
        history_qs = history_qs.filter(decision=decision)
    if date_from:
        history_qs = history_qs.filter(checked_at__date__gte=date_from)
    if date_to:
        history_qs = history_qs.filter(checked_at__date__lte=date_to)

    # Summary counts
    total_count = history_qs.count()
    allow_count = history_qs.filter(decision='allow').count()
    deny_count = history_qs.filter(decision='deny').count()
    limited_count = history_qs.filter(decision='limited').count()

    # Paginate
    paginator = Paginator(history_qs, 10)
    page = request.GET.get('page')
    try:
        history_page = paginator.page(page)
    except PageNotAnInteger:
        history_page = paginator.page(1)
    except EmptyPage:
        history_page = paginator.page(paginator.num_pages)

    # Patient list for filter dropdown
    patients = Patient.objects.select_related('user').order_by('user__first_name', 'user__last_name')

    context = {
        'history': history_page,
        'patients': patients,
        'filters': {
            'patient_id': patient_id,
            'resource_type': resource_type,
            'purpose': purpose,
            'decision': decision,
            'date_from': date_from,
            'date_to': date_to,
        },
        'total_count': total_count,
        'allow_count': allow_count,
        'deny_count': deny_count,
        'limited_count': limited_count,
        'resource_type_choices': [
            ('lab_results', 'Lab Results'),
            ('diagnosis', 'Diagnosis'),
            ('mental_health', 'Mental Health'),
            ('medication', 'Medication'),
            ('billing', 'Billing'),
            ('treatment', 'Treatment'),
            ('allergies', 'Allergies'),
            ('immunization', 'Immunization'),
        ],
        'purpose_choices': [
            ('treatment', 'Treatment'),
            ('research', 'Research'),
            ('audit', 'Audit'),
            ('emergency', 'Emergency'),
            ('insurance', 'Insurance'),
        ],
        'decision_choices': [
            ('allow', 'Allow'),
            ('limited', 'Limited'),
            ('deny', 'Deny'),
        ],
    }
    return render(request, 'pages/access_history.html', context)