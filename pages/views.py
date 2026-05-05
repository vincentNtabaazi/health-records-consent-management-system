import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Q
from django.shortcuts import render
from django.shortcuts import render, redirect

from consents.models import Consent
from patients.models import MedicalRecord, Patient
from users.models import User, Role, CustomPermission
from services.odrl import infer_data_category_from_permission
from datetime import datetime
from django.db.models import Count
from services.datasetGenerator import generate_dataset
from services.generate_medical_records import populate_medical_records, generate_medical_permissions
from users.models import User
from users.utils import get_role
from django.contrib import messages
from consents.models import AccessRequest, DecisionLog
from services.policy_engine import evaluate_access
from services.compliance_checker import check_violations
from django.utils import timezone
from datetime import timedelta



@login_required(login_url='users:login_view')
def home(request):
    role = get_role(request)
    return render(request, 'pages/home.html', locals())


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
        # If page is not an integer, deliver first page.
        data_subjects_list = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
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
    all_patients = Patient.objects.all()
    last_30_days = timezone.now() - timedelta(days=30)

    context = {
        'consent_total': all_consents.count(),
        'consent_active': all_consents.filter(status='active').count(),
        'consent_pending': all_consents.filter(status='pending').count(),
        'consent_withdrawn': all_consents.filter(status='withdrawn').count(),
        'consent_denied': all_consents.filter(status='denied').count(),
        'recent_consents': all_consents.select_related('patient', 'data_processor')[:5],
        'all_patients': all_patients.count(),
        'new_patients_last_30_days': all_patients.filter(user__created_at__gte=last_30_days).count(),
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
        'paginator':paginator,
        'is_paginated': page_obj.has_other_pages(),
    }
    return render(request, 'pages/medical_records.html', context)


from django.contrib import messages
from consents.models import AccessRequest, DecisionLog
from services.policy_engine import evaluate_access
from services.compliance_checker import check_violations, get_expiring_consents_for_patient, auto_expire_consents


def build_requester_scoped_compliance_report(logs):
    logs = list(logs)

    total_requests = len(logs)
    allowed = sum(1 for log in logs if log.decision == 'allow')
    denied = sum(1 for log in logs if log.decision == 'deny')
    redacted = sum(1 for log in logs if log.decision == 'limited')
    violations = []

    for log in logs:
        access_request = log.access_request

        if log.compliance_status == 'non_compliant':
            violations.append({
                'type': 'NON_COMPLIANT_DECISION',
                'severity': 'HIGH',
                'requester': access_request.requester,
                'resource_type': access_request.resource_type,
                'checked_at': log.checked_at,
                'details': log.reason,
            })

        if not access_request.purpose and log.decision == 'allow':
            violations.append({
                'type': 'EMPTY_PURPOSE_ALLOWED',
                'severity': 'MEDIUM',
                'requester': access_request.requester,
                'resource_type': access_request.resource_type,
                'checked_at': log.checked_at,
                'details': 'Access was allowed even though the purpose was empty.',
            })

        if log.matched_consent is None and log.decision == 'allow':
            violations.append({
                'type': 'ALLOW_WITHOUT_CONSENT',
                'severity': 'HIGH',
                'requester': access_request.requester,
                'resource_type': access_request.resource_type,
                'checked_at': log.checked_at,
                'details': 'Access was allowed without a matched consent record.',
            })

    compliance_rate = 100
    if total_requests > 0:
        compliant_count = total_requests - len(violations)
        compliance_rate = round((compliant_count / total_requests) * 100, 1)

    return {
        'total_requests': total_requests,
        'allowed': allowed,
        'denied': denied,
        'redacted': redacted,
        'compliance_rate': compliance_rate,
        'violations': violations,
    }

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


def get_visible_decision_logs_for_user(user):
    role = getattr(getattr(user, 'role', None), 'name', None)
    is_global_auditor = user.is_staff or user.is_superuser or role == 'regulator'

    base_logs = DecisionLog.objects.select_related(
        'access_request',
        'access_request__requester',
        'access_request__requester__role',
        'access_request__patient',
        'access_request__patient__user',
        'matched_consent',
    )

    if is_global_auditor:
        return base_logs.all()

    if role == 'subject':
        try:
            subject_patient = Patient.objects.get(user=user)
            return base_logs.filter(access_request__patient=subject_patient)
        except Patient.DoesNotExist:
            return base_logs.none()

    return base_logs.filter(access_request__requester=user)


@login_required(login_url='users:login_view')
def compliance_dashboard_view(request):
    role = getattr(getattr(request.user, 'role', None), 'name', None)
    is_global_auditor = request.user.is_staff or request.user.is_superuser or role == 'regulator'

    if role == 'subject':
        messages.info(request, 'Patients can view their access transparency report in My Data.')
        return redirect('pages:my_data')

    selected_patient = None
    report = None

    base_logs = DecisionLog.objects.select_related(
        'access_request',
        'access_request__requester',
        'access_request__requester__role',
        'access_request__patient',
        'access_request__patient__user',
        'matched_consent',
    )

    if is_global_auditor:
        visible_logs = base_logs.all()
        patients = Patient.objects.select_related('user').all()
        dashboard_scope = 'global'
        scope_description = 'You can inspect all access decisions and compliance events across the system.'
    elif role == 'subject':
        try:
            subject_patient = Patient.objects.get(user=request.user)
            visible_logs = base_logs.filter(access_request__patient=subject_patient)
            patients = Patient.objects.filter(id=subject_patient.id).select_related('user')
            selected_patient = subject_patient
            dashboard_scope = 'subject'
            scope_description = 'You can only view access decisions related to your own health data.'
        except Patient.DoesNotExist:
            visible_logs = base_logs.none()
            patients = Patient.objects.none()
            dashboard_scope = 'subject'
            scope_description = 'No patient profile is linked to your account.'
    else:
        visible_logs = base_logs.filter(access_request__requester=request.user)
        patient_ids = visible_logs.values_list('access_request__patient_id', flat=True).distinct()
        patients = Patient.objects.filter(id__in=patient_ids).select_related('user')
        dashboard_scope = 'requester'
        scope_description = 'You can only view access decisions for requests submitted by your account.'

    patient_id = request.GET.get('patient_id')
    if patient_id:
        try:
            candidate_patient = patients.get(id=patient_id)
            selected_patient = candidate_patient

            if is_global_auditor or role == 'subject':
                report = check_violations(selected_patient)
            else:
                patient_logs = visible_logs.filter(access_request__patient=selected_patient)
                report = build_requester_scoped_compliance_report(patient_logs)

        except Patient.DoesNotExist:
            messages.error(request, 'You are not allowed to audit this patient or the patient was not found.')

    if role == 'subject' and selected_patient and report is None:
        report = check_violations(selected_patient)

    decision_filter = request.GET.get('decision', 'all')
    compliance_filter = request.GET.get('compliance', 'all')

    filtered_logs = visible_logs

    if decision_filter in ['allow', 'deny', 'limited']:
        filtered_logs = filtered_logs.filter(decision=decision_filter)

    if compliance_filter in ['compliant', 'non_compliant']:
        filtered_logs = filtered_logs.filter(compliance_status=compliance_filter)

    recent_logs = filtered_logs.order_by('-checked_at')[:20]

    total_visible_logs = visible_logs.count()
    allowed_count = visible_logs.filter(decision='allow').count()
    denied_count = visible_logs.filter(decision='deny').count()
    redacted_count = visible_logs.filter(decision='limited').count()
    non_compliant_count = visible_logs.filter(compliance_status='non_compliant').count()

    context = {
        'patients': patients,
        'selected_patient': selected_patient,
        'report': report,
        'recent_logs': recent_logs,
        'decision_filter': decision_filter,
        'compliance_filter': compliance_filter,
        'dashboard_scope': dashboard_scope,
        'scope_description': scope_description,
        'is_global_auditor': is_global_auditor,
        'total_visible_logs': total_visible_logs,
        'allowed_count': allowed_count,
        'denied_count': denied_count,
        'redacted_count': redacted_count,
        'non_compliant_count': non_compliant_count,
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
@login_required(login_url='users:login_view')
def export_audit_logs_csv(request):
    logs = get_visible_decision_logs_for_user(request.user).order_by('-checked_at')

    decision_filter = request.GET.get('decision', 'all')
    compliance_filter = request.GET.get('compliance', 'all')
    patient_id = request.GET.get('patient_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if decision_filter in ['allow', 'deny', 'limited']:
        logs = logs.filter(decision=decision_filter)

    if compliance_filter in ['compliant', 'non_compliant']:
        logs = logs.filter(compliance_status=compliance_filter)

    if patient_id:
        logs = logs.filter(access_request__patient_id=patient_id)

    if start_date:
        logs = logs.filter(checked_at__date__gte=start_date)

    if end_date:
        logs = logs.filter(checked_at__date__lte=end_date)

    response = HttpResponse(content_type='text/csv')

    filename = f'audit_logs_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(['Generated At', datetime.now().strftime('%d-%b-%Y %H:%M')])
    writer.writerow(['Export Scope', 'Role-scoped audit logs based on current user permissions'])
    writer.writerow([])

    writer.writerow([
        'Checked At',
        'Requester',
        'Requester Role',
        'Patient',
        'Resource Type',
        'Purpose',
        'Action',
        'Decision',
        'Compliance Status',
        'Matched Consent',
        'Reason',
    ])

    for log in logs:
        access_request = log.access_request
        requester = access_request.requester
        requester_role = getattr(getattr(requester, 'role', None), 'name', '')

        writer.writerow([
            log.checked_at.strftime('%d-%b-%Y %H:%M') if log.checked_at else '',
            requester.username if requester else '',
            requester_role,
            str(access_request.patient) if access_request.patient else '',
            access_request.resource_type,
            access_request.purpose,
            access_request.action,
            log.decision,
            log.compliance_status,
            log.matched_consent.consent_id if log.matched_consent else '',
            log.reason.replace('\n', ' ') if log.reason else '',
        ])

    return response


@login_required(login_url='users:login_view')
def my_data_view(request):
    # Only for subject role
    role = getattr(getattr(request.user, 'role', None), 'name', None)
    if role != 'subject':
        messages.error(request, 'This page is only accessible to patients.')
        return redirect('pages:dashboard_view')

    # Get patient profile
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('pages:dashboard_view')

    # Auto-expire any consents that have passed their expiry date
    auto_expire_consents()

    # Find consents expiring within the next 7 days
    expiring_consents = get_expiring_consents_for_patient(request.user, days_ahead=7)

    # Who accessed my data
    access_logs = DecisionLog.objects.filter(
        access_request__patient=patient
    ).select_related(
        'access_request',
        'access_request__requester',
        'access_request__requester__role',
        'matched_consent',
    ).order_by('-checked_at')

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
        'allow_count':   access_logs.filter(decision='allow').count(),
        'deny_count':    access_logs.filter(decision='deny').count(),
        'redact_count':  access_logs.filter(decision='limited').count(),
        'expiring_consents': expiring_consents,
    }
    return render(request, 'pages/my_data.html', context)