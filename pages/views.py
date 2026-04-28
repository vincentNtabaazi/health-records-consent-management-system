from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q
from django.shortcuts import render

from consents.models import Consent
from patients.models import MedicalRecord, Patient


@login_required(login_url='users:login_view')
def home(request):
    return render(request, 'pages/home.html')


@login_required(login_url='users:login_view')
def data_subjects(request):
    search_query = (request.GET.get('q') or '').strip()
    selected_organization = (request.GET.get('organization') or '').strip()

    organizations = list(
        Patient.objects
        .exclude(user__organization_name__isnull=True)
        .exclude(user__organization_name__exact='')
        .values('user__organization_name')
        .annotate(subject_count=Count('id'))
        .order_by('user__organization_name')
    )

    data_subjects_qs = Patient.objects.select_related('user').order_by(
        'user__organization_name',
        'user__last_name',
        'user__first_name',
        'id',
    )

    if selected_organization:
        data_subjects_qs = data_subjects_qs.filter(
            user__organization_name=selected_organization
        )

    if search_query:
        for term in search_query.split():
            data_subjects_qs = data_subjects_qs.filter(
                Q(user__first_name__icontains=term)
                | Q(user__last_name__icontains=term)
                | Q(user__email__icontains=term)
                | Q(user__username__icontains=term)
            )

    total_subjects = data_subjects_qs.count()
    paginator = Paginator(data_subjects_qs, 6)
    page = request.GET.get('page')

    try:
        data_subjects_list = paginator.page(page)
    except PageNotAnInteger:
        data_subjects_list = paginator.page(1)
    except EmptyPage:
        data_subjects_list = paginator.page(paginator.num_pages)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    page_querystring = query_params.urlencode()
    page_prefix = f'?{page_querystring}&' if page_querystring else '?'

    return render(request, 'pages/data_subjects.html', {
        'data_subjects_list': data_subjects_list,
        'organizations': organizations,
        'search_query': search_query,
        'selected_organization': selected_organization,
        'total_subjects': total_subjects,
        'page_prefix': page_prefix,
    })


@login_required(login_url='users:login_view')
def consent_records(request):
    consent_list = Consent.objects.select_related('patient', 'data_processor')

    if request.user.is_staff or request.user.is_superuser:
        consent_list = consent_list.all()
    elif getattr(getattr(request.user, 'role', None), 'name', None) == 'subject':
        consent_list = consent_list.filter(patient=request.user)
    else:
        consent_list = consent_list.filter(data_processor=request.user)

    consent_list = consent_list.order_by('-id')
    paginator = Paginator(consent_list, 6)
    page = request.GET.get('page')

    try:
        consents = paginator.page(page)
    except PageNotAnInteger:
        consents = paginator.page(1)
    except EmptyPage:
        consents = paginator.page(paginator.num_pages)

    context = {
        'consents': consents,
        'is_paginated': True,
        'page_obj': consents,
        'paginator': paginator,
    }
    return render(request, 'pages/consent_records.html', context)


@login_required(login_url='users:login_view')
def policies(request):
    return render(request, 'pages/policies.html')


@login_required(login_url='users:login_view')
def dashboard_view(request):
    all_consents = Consent.objects.all()
    context = {
        'consent_total': all_consents.count(),
        'consent_active': all_consents.filter(status='active').count(),
        'consent_pending': all_consents.filter(status='pending').count(),
        'consent_withdrawn': all_consents.filter(status='withdrawn').count(),
        'recent_consents': all_consents.select_related('patient', 'data_processor')[:5],
        'recent_patients': Patient.objects.select_related('user').order_by('-id')[:5],
    }
    return render(request, 'pages/dashboard.html', context)


@login_required(login_url='users:login_view')
def medical_records(request):
    all_records = MedicalRecord.objects.select_related(
        'patient',
        'patient__user'
    ).order_by('-created_at')

    paginator = Paginator(all_records, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    category_counts = MedicalRecord.objects.values('data_category').annotate(
        count=Count('data_category')
    )
    category_counts_dict = {
        dict(MedicalRecord.DATA_CATEGORY_CHOICES).get(
            item['data_category'],
            item['data_category']
        ): item['count']
        for item in category_counts
    }

    context = {
        'medical_records': page_obj,
        'category_counts': category_counts_dict,
    }
    return render(request, 'pages/medical_records.html', context)


from django.contrib import messages
from consents.models import AccessRequest, DecisionLog
from services.policy_engine import evaluate_access
from services.compliance_checker import check_violations


@login_required(login_url='users:login_view')
def access_request_view(request):
    patients = Patient.objects.select_related('user').all()

    if request.method == 'POST':
        patient_id = request.POST.get('patient_id')
        resource_type = request.POST.get('resource_type')
        purpose = request.POST.get('purpose')
        action = request.POST.get('action', 'read')

        try:
            patient = Patient.objects.get(id=patient_id)
            log = evaluate_access(
                requester=request.user,
                patient=patient,
                resource_type=resource_type,
                purpose=purpose,
                action=action,
            )
            context = {
                'patients': patients,
                'result': log,
                'decision': log.decision,
                'reason': log.reason,
                'submitted': True,
            }
            return render(request, 'pages/access_request.html', context)

        except Patient.DoesNotExist:
            messages.error(request, 'Patient not found.')

    return render(request, 'pages/access_request.html', {'patients': patients})


@login_required(login_url='users:login_view')
def compliance_dashboard_view(request):
    patients = Patient.objects.select_related('user').all()
    selected_patient = None
    report = None

    patient_id = request.GET.get('patient_id')
    if patient_id:
        try:
            selected_patient = Patient.objects.get(id=patient_id)
            report = check_violations(selected_patient)
        except Patient.DoesNotExist:
            messages.error(request, 'Patient not found.')

    recent_logs = DecisionLog.objects.select_related(
        'access_request',
        'access_request__requester',
        'access_request__patient',
    ).order_by('-checked_at')[:20]

    context = {
        'patients': patients,
        'selected_patient': selected_patient,
        'report': report,
        'recent_logs': recent_logs,
    }
    return render(request, 'pages/compliance_dashboard.html', context)


@login_required(login_url='users:login_view')
def my_data_view(request):
    """Show a subject who accessed their data and their consent records."""
    patient = Patient.objects.filter(user=request.user).first()

    if patient:
        access_logs = (
            DecisionLog.objects
            .select_related(
                'access_request',
                'access_request__requester',
                'access_request__requester__role',
                'matched_consent',
            )
            .filter(access_request__patient=patient)
            .order_by('-checked_at')
        )
    else:
        access_logs = DecisionLog.objects.none()
        messages.info(
            request,
            'No subject profile was found for your account yet.'
        )

    my_consents = (
        Consent.objects
        .select_related('data_processor', 'data_processor__role')
        .filter(patient=request.user)
        .order_by('-created_date')
    )

    context = {
        'access_logs': access_logs,
        'allow_count': access_logs.filter(decision='allow').count(),
        'redact_count': access_logs.filter(decision='limited').count(),
        'deny_count': access_logs.filter(decision='deny').count(),
        'my_consents': my_consents,
    }
    return render(request, 'pages/my_data.html', context)