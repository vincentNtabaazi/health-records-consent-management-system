from django.shortcuts import render, get_object_or_404
from patients.models import Patient, MedicalRecord
from users.models import Role, RolePermission
from patients.models import PatientPermission


def get_patient_roles_permissions(patient):

    results = {}

    patient_perms = (
        PatientPermission.objects
        .filter(patient=patient)
        .select_related("role_permission__role", "role_permission__permission")
    )

    for pp in patient_perms:
        role = pp.role_permission.role
        permission = pp.role_permission.permission

        if role.id not in results:
            results[role.id] = []

        results[role.id].append({
            "id": permission.id,
            "name": permission.name
        })

    return results



def patient_medical_timeline(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)
    medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-created_at')

    # Example for upcoming appointments (you'd have a separate model for this)
    # For now, just dummy data or an empty list
    upcoming_appointments = [
        {'title': 'Annual Check-up', 'date_time': '2024-03-10 10:00', 'doctor_name': 'Dr. Evans'},
        {'title': 'Dental Cleaning', 'date_time': '2024-04-01 14:30', 'doctor_name': 'Dr. White'},
    ]

    roles = Role.objects.all().exclude(name__in=['Admin', 'subject'])
    permissions = get_patient_roles_permissions(patient)
    all_permissions = RolePermission.objects.all()
    print(all_permissions)
    """ You stopped here, you are trying to get all the permissions the different roles can have on the system 
    so that you can display them and a user can select which ones he wants to give to the patient
    Then the next step is the consent records from here"""

    return render(request, 'pages/datasubject_details.html', locals())