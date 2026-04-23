from django.contrib import messages
from django.shortcuts import render, get_object_or_404

from consents.models import Consent
from patients.models import Patient, MedicalRecord
from users.models import Role, RolePermission
from patients.models import PatientPermission
from django.shortcuts import redirect
from django.db import transaction

def get_roles_permissions(patient=None, patient_permissions=None):
    results = {}

    if patient:
        # Patient-specific permissions
        patient_perms = (
            PatientPermission.objects
            .filter(patient=patient)
            .select_related("role_permission__role", "role_permission__permission")
        )

        for pp in patient_perms:
            role = pp.role_permission.role
            permission = pp.role_permission.permission

            results.setdefault(role.id, []).append({
                "id": permission.id,
                "name": permission.name
            })

    else:
        # All role-permission mappings
        role_permissions = (
            RolePermission.objects
            .select_related("role", "permission")
        )

        # Convert patient_permissions → fast lookup (role_id → set of permission_ids)
        patient_perm_map = {}

        if patient_permissions:
            for role_id, perms in patient_permissions.items():
                patient_perm_map[role_id] = {p["id"] for p in perms}

        for rp in role_permissions:
            role = rp.role
            permission = rp.permission

            # Check if assigned
            is_assigned = False
            if role.id in patient_perm_map:
                is_assigned = permission.id in patient_perm_map[role.id]

            results.setdefault(role.id, []).append({
                "id": permission.id,
                "name": permission.name,
                "is_assigned": is_assigned
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
    permissions = get_roles_permissions(patient)
    all_permissions = get_roles_permissions(patient_permissions=permissions)
    consents = Consent.objects.filter(patient=patient.user)
    """ 
    TODO: Then the next step is the consent records from here, the consents are now working fine. We shall consider that 
    that if a user consents then any records on the system under that category where he consented are visible to the 
    role he consented them to. I want to add a part where he could maybe deny the documents to a particular processor or
    researcher for any reason they choose to.
    """

    return render(request, 'pages/datasubject_details.html', locals())


def update_patient_permissions(request, patient_id):
    if request.method == "POST":
        patient = Patient.objects.get(id=patient_id)

        ## Clear existing permissions for this role (optional)
        with transaction.atomic():
            PatientPermission.objects.filter(
                patient=patient
            ).delete()

            ## Regenerate the permissions

            for key in request.POST:
                if key.startswith("permissions_"):
                    role_id = key.split("_")[1].replace("[]", "")
                    permission_ids = request.POST.getlist(key)
                    print(role_id, permission_ids)
                    for perm_id in permission_ids:
                        role_perm = RolePermission.objects.filter(
                            role_id=role_id,
                            permission_id=perm_id
                        ).first()
                        PatientPermission.objects.create(
                            patient=patient,
                            role_permission=role_perm
                        )
            messages.success(request, "Patient Consents updated successfully.")
            return redirect(request.POST.get("next", request.META.get('HTTP_REFERER', '/')))

    messages.danger(request, "Unexpected error !!!")
    return redirect(request.POST.get("next", request.META.get('HTTP_REFERER', '/')))