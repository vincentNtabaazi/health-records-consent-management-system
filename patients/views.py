from django.shortcuts import render, get_object_or_404
from patients.models import Patient, MedicalRecord


# Create your views here.
def patient_medical_timeline(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)

    # Fetch medical records for the patient.
    # The template uses patient.medicalrecord_set.all, but fetching here
    # can allow for prefetching or more complex queries.
    medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-created_at')

    # Example for upcoming appointments (you'd have a separate model for this)
    # For now, just dummy data or an empty list
    upcoming_appointments = [
        {'title': 'Annual Check-up', 'date_time': '2024-03-10 10:00', 'doctor_name': 'Dr. Evans'},
        {'title': 'Dental Cleaning', 'date_time': '2024-04-01 14:30', 'doctor_name': 'Dr. White'},
    ]
    # You would typically query an Appointment model like:
    # from datetime import datetime, timedelta
    # upcoming_appointments = patient.appointment_set.filter(date_time__gte=datetime.now()).order_by('date_time')

    context = {
        'patient': patient,
        'medical_records': medical_records, # Can pass explicitly or let template access via patient.medicalrecord_set
        'upcoming_appointments': upcoming_appointments,
    }
    return render(request, 'pages/datasubject_details.html', context)