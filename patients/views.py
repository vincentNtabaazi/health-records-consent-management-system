from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from consents.models import Consent
from patients.models import Patient, MedicalRecord
from users.models import Role, RolePermission
from patients.models import PatientPermission
from services.policy_engine import check_access


def get_patient_roles_permissions(patient):
    results = {}
    patient_perms = (
        PatientPermission.objects
        .filter(patient=patient)
        .select_related('role_permission__role', 'role_permission__permission')
    )

    for pp in patient_perms:
        role = pp.role_permission.role
        permission = pp.role_permission.permission

        if role.id not in results:
            results[role.id] = []

        results[role.id].append({
            'id': permission.id,
            'name': permission.name,
        })

    return results


@login_required(login_url='users:login_view')
def patient_medical_timeline(request, patient_id):
    patient = get_object_or_404(Patient.objects.select_related('user'), pk=patient_id)
    all_medical_records = MedicalRecord.objects.filter(patient=patient).order_by('-created_at')

    can_review_all_patient_requests = (
        request.user.is_staff
        or request.user.is_superuser
        or request.user.id == patient.user_id
        or patient.user.delegated_to_id == request.user.id
    )
    can_manage_sharing_preferences = (
        getattr(getattr(request.user, 'role', None), 'name', None) == 'subject'
        and request.user.id == patient.user_id
    )

    if can_review_all_patient_requests:
        medical_records = list(all_medical_records)
    else:
        medical_records = [
            record
            for record in all_medical_records
            # TODO: This function has an issue 
            # if check_access(request.user, record, 'read')
        ]

    upcoming_appointments = [
        {'title': 'Annual Check-up', 'date_time': '2026-05-10 10:00', 'doctor_name': 'Dr. Evans'},
        {'title': 'Dental Cleaning', 'date_time': '2026-06-01 14:30', 'doctor_name': 'Dr. White'},
    ]

    roles = Role.objects.exclude(name='subject')
    permissions = get_patient_roles_permissions(patient)
    role_permission_matrix = (
        RolePermission.objects
        .select_related('role', 'permission')
        .order_by('role__name', 'permission__name')
    )

    if can_review_all_patient_requests:
        pending_consents = (
            Consent.objects
            .select_related('data_processor', 'data_processor__role')
            .filter(patient=patient.user, status='pending')
            .order_by('-created_date')
        )
        active_consents = (
            Consent.objects
            .select_related('data_processor', 'data_processor__role')
            .filter(patient=patient.user, status='active')
            .order_by('-created_date')
        )
    else:
        pending_consents = (
            Consent.objects
            .select_related('data_processor', 'data_processor__role')
            .filter(patient=patient.user, data_processor=request.user, status='pending')
            .order_by('-created_date')
        )
        active_consents = (
            Consent.objects
            .select_related('data_processor', 'data_processor__role')
            .filter(patient=patient.user, data_processor=request.user, status='active')
            .order_by('-created_date')
        )

    return render(request, 'pages/datasubject_details.html', {
        'patient': patient,
        'medical_records': medical_records,
        'upcoming_appointments': upcoming_appointments,
        'roles': roles,
        'permissions': permissions,
        'role_permission_matrix': role_permission_matrix,
        'pending_consents': pending_consents,
        'active_consents': active_consents,
        'can_manage_sharing_preferences': can_manage_sharing_preferences,
    })