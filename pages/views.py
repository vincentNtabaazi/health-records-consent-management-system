from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from consents.models import Consent
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from patients.models import MedicalRecord, Patient
from django.db.models import Count
from services.generate_medical_records import populate_medical_records
from users.models import User


@login_required(login_url='users:login_view')
def home(request):
    return render(request, 'pages/home.html')

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

def consent_records(request):
    consent_list = Consent.objects.all().order_by('-id')
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

def policies(request):
    return render(request, 'pages/policies.html')

def dashboard_view(request):
    populate_medical_records()
    return render(request, 'pages/dashboard.html')

def medical_records(request):
    # Fetch all medical records, ordered by creation date (most recent first)
    all_records = MedicalRecord.objects.select_related('patient').order_by('-created_at')

    # Apply pagination
    paginator = Paginator(all_records, 10)  # Show 10 records per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Optional: Get counts for each category
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