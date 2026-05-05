def subject_context(request):
    """Add patient_id to context for subject users."""
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'role', None), 'name', None)
        if role == 'subject':
            from patients.models import Patient
            try:
                patient = Patient.objects.get(user=request.user)
                return {'subject_patient_id': patient.id}
            except Patient.DoesNotExist:
                pass
    return {}