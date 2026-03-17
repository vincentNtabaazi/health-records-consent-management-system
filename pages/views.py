from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from consents.models import Consent
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from users.models import User


@login_required(login_url='users:login_view')
def home(request):
    return render(request, 'pages/home.html')

def data_subjects(request):
    data_subjects_list = User.objects.filter(role_id=6).order_by('id')

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
    return render(request, 'pages/dashboard.html')