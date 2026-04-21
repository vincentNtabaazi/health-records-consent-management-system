from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from django.shortcuts import render

from consents.models import Consent
from patients.models import MedicalRecord, Patient


@login_required(login_url='users:login_view')
def home(request):
    return render(request, 'pages/home.html')


@login_required(login_url='users:login_view')
def data_subjects(request):
    data_subjects_list = Patient.objects.select_related('user').order_by('id')
    paginator = Paginator(data_subjects_list, 6)
    page = request.GET.get('page')
    try:
        data_subjects_list = paginator.page(page)
    except PageNotAnInteger:
        data_subjects_list = paginator.page(1)
    except EmptyPage:
        data_subjects_list = paginator.page(paginator.num_pages)

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

    context = {
        'medical_records': page_obj,
        'category_counts': category_counts_dict,
    }
    return render(request, 'pages/medical_records.html', context)
