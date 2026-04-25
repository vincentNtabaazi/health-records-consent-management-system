from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from django.shortcuts import render

from consents.models import Consent
from patients.models import MedicalRecord, Patient
from django.db.models import Count
from services.datasetGenerator import generate_dataset
from services.generate_medical_records import populate_medical_records, generate_medical_permissions
from users.models import User
from users.utils import get_role
from django.contrib import messages
from consents.models import AccessRequest, DecisionLog
from services.policy_engine import evaluate_access
from services.compliance_checker import check_violations



@login_required(login_url='users:login_view')
def home(request):
    role = get_role(request)
    return render(request, 'pages/home.html', locals())


@login_required(login_url='users:login_view')
def data_subjects(request):
    data_subjects_list = Patient.objects.select_related('user').order_by('id')
    paginator = Paginator(data_subjects_list, 6)
    page = request.GET.get('page')
    try:
        data_subjects_list = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        data_subjects_list = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        data_subjects_list = paginator.page(paginator.num_pages)

    # Note: Using 'data_subjects' as the context variable name now,
    # which is consistent with the template usage.
    return render(request, 'pages/data_subjects.html', {'data_subjects_list': data_subjects_list})


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
    all_records = MedicalRecord.objects.select_related('patient', 'patient__user').order_by('-created_at')
    paginator = Paginator(all_records, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    category_counts = MedicalRecord.objects.values('data_category').annotate(count=Count('data_category'))
    category_counts_dict = {
        dict(MedicalRecord.DATA_CATEGORY_CHOICES).get(item['data_category'], item['data_category']): item['count']
        for item in category_counts
    }
    print(page_obj)
    context = {
        'medical_records': page_obj,
        'category_counts': category_counts_dict,
        'paginator':paginator,
        'is_paginated': page_obj.has_other_pages(),
    }
    return render(request, 'pages/medical_records.html', context)

@login_required(login_url='users:login_view')
def access_request_view(request):
    patients = Patient.objects.select_related('user').all()

    if request.method == 'POST':
        patient_id    = request.POST.get('patient_id')
        resource_type = request.POST.get('resource_type')
        purpose       = request.POST.get('purpose')
        action        = request.POST.get('action', 'read')

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
                'patients':      patients,
                'result':        log,
                'decision':      log.decision,
                'reason':        log.reason,
                'submitted':     True,
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
        'patients':         patients,
        'selected_patient': selected_patient,
        'report':           report,
        'recent_logs':      recent_logs,
    }
    return render(request, 'pages/compliance_dashboard.html', context)