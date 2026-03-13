from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from consents.models import Consent


# Create your views here.

@login_required(login_url='users:login_view')
def home(request):
    return render(request, 'pages/home.html')

def data_subjects(request):
    return render(request, 'pages/data_subjects.html')

def consent_records(request):
    consents = Consent.objects.all()
    return render(request, 'pages/consent_records.html', locals())

def policies(request):
    return render(request, 'pages/policies.html')

def data_subjects(request):
    return render(request, 'pages/data_subjects.html')