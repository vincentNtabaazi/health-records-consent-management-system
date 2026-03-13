from django.shortcuts import render

# Create your views here.

def consent_details(request, consent_id):
    return render(request, 'consents/consent_details.html')