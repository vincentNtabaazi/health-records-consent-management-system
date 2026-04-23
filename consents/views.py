from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import *

# Create your views here.

def consent_details(request, consent_id):
    return render(request, 'consents/consent_details.html')

def consent_withdraw(request):
    if request.method == "POST":
        consent_id = request.POST.get('consent_id')
        consent = get_object_or_404(Consent, id=consent_id)
        consent.withdraw_consent()
        messages.success(request, "Consent withdrawn successfully.")
    return redirect(request.POST.get("next", request.META.get('HTTP_REFERER', '/')))