from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from consents.models import Consent
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from patients.models import MedicalRecord, Patient
from django.db.models import Count
from services.datasetGenerator import generate_dataset
from services.generate_medical_records import populate_medical_records, generate_medical_permissions
from users.models import User
from users.utils import get_role


@login_required(login_url='users:login_view')
def home(request):
    role = get_role(request)
    return render(request, 'pages/home.html', locals())

def data_subjects(request):
    data_subjects_list = Patient.objects.filter().order_by('id')

    # Set up Paginator
    paginator = Paginator(data_subjects_list, 6)  # Show 6 data subjects per page

    page = request.GET.get('page') # Get the current page number from the URL
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

def medical_records(request):
    role = get_role(request)
    consent_list = generate_dataset(request.user.role).order_by('-id')
    paginator = Paginator(consent_list, 6)

    page = request.GET.get('page')
    try:
        consents = paginator.page(page)
    except PageNotAnInteger:
        consents = paginator.page(1)
    except EmptyPage:
        consents = paginator.page(paginator.num_pages)

    return render(request, 'pages/medical_records.html', {
        'consents': consents,
        'paginator': paginator,
        'page_obj': consents,
        'is_paginated': paginator.num_pages > 1,
        'role': role,
    })

def policies(request):
    return render(request, 'pages/policies.html')

@login_required(login_url='users:login_view')
def dashboard_view(request):
    # generate_medical_permissions()
    role = get_role(request)
    return render(request, 'pages/dashboard.html', locals())
