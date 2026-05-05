from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import *
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from consents.forms import ConsentRequestForm, SubjectSharingPreferencesForm, ALLOWED_REQUESTER_ROLES
from consents.models import Consent
from patients.models import MedicalRecord, Patient, PatientPermission
from users.models import CustomPermission
from services.odrl import infer_action_from_permission, infer_data_category_from_permission, prettify_permission
from services.policy_engine import check_access



def _can_request(user):
    return user.is_authenticated and getattr(getattr(user, 'role', None), 'name', None) in ALLOWED_REQUESTER_ROLES



def _can_review(user, consent):
    """
    Check if user can review/approve this consent.
    Note: For GRANTED_BY_SUBJECT, only the data_processor (not the subject) can approve.
    """
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    # Don't allow subject to review their own granted consent - only data processor can approve
    if consent.patient_id == user.id and consent.consent_type == 'GRANTED_BY_SUBJECT':
        return False
    # Allow data processor (researcher/processor/regulator/agent) to review GRANTED_BY_SUBJECT
    if consent.data_processor_id == user.id and consent.consent_type == 'GRANTED_BY_SUBJECT':
        return True
    if consent.patient_id == user.id:
        return True
    if consent.patient.delegated_to_id == user.id:
        return True
    return False



def _can_manage_subject_preferences(user, patient):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if patient.user_id == user.id:
        return True
    if patient.user.delegated_to_id == user.id:
        return True
    return False



def _subject_preconsented_permission_ids(patient, role):
    return set(
        PatientPermission.objects
        .filter(patient=patient, role_permission__role=role)
        .values_list('role_permission__permission_id', flat=True)
    )


@login_required(login_url='users:login_view')
def request_consent_view(request, patient_id):
    if not _can_request(request.user):
        raise PermissionDenied('Your role cannot request consent.')

    patient = get_object_or_404(Patient.objects.select_related('user'), pk=patient_id)
    preconsented_permission_ids = _subject_preconsented_permission_ids(patient, request.user.role)

    if request.method == 'POST':
        form = ConsentRequestForm(request.POST, requester=request.user)
        if form.is_valid():
            permission_ids = form.cleaned_data['permission_ids']
            permissions = list(CustomPermission.objects.filter(id__in=permission_ids))
            categories = sorted({infer_data_category_from_permission(perm.name) for perm in permissions})

            # Check for duplicate consent (same logic as grant consent)
            expiry_date_obj = form.cleaned_data.get('expiry_date')
            existing_consents = Consent.objects.filter(
                patient=patient.user,
                data_processor=request.user,
                expiry_date=expiry_date_obj,
                status__in=['pending', 'active']
            )

            # Collect ALL permissions from ALL existing consents
            all_existing_perms = set()
            for c in existing_consents:
                all_existing_perms.update(str(p) for p in c.requested_permissions)

            # Check if ALL requested permissions are already covered
            permission_ids_as_str = [str(pid) for pid in permission_ids]
            input_perms_set = set(permission_ids_as_str)
            existing_consent = None
            if input_perms_set.issubset(all_existing_perms):
                # Already have consent covering these permissions
                existing_consent = existing_consents.first()

            # If duplicate and no confirmation, show confirmation page
            if existing_consent and not request.POST.get('confirm_create'):
                context = {
                    'patient': patient,
                    'form': form,
                    'grouped_permissions': form.grouped_permissions,
                    'selected_permission_ids': {str(value) for value in request.POST.getlist('permission_ids')},
                    'preconsented_permission_ids': {str(item) for item in preconsented_permission_ids},
                    'duplicate_warning': True,
                    'existing_consent': existing_consent,
                    'confirm_data': {
                        'patient_id': patient_id,
                        'permission_ids': permission_ids,
                        'purpose': form.cleaned_data.get('purpose'),
                        'expiry_date': form.cleaned_data.get('expiry_date'),
                        'notes': form.cleaned_data.get('notes'),
                    }
                }
                return render(request, 'consents/request_consent.html', context)

            consent = form.save(commit=False)
            consent.patient = patient.user
            consent.data_processor = request.user
            consent.data_type = ', '.join(categories)
            consent.requested_permissions = permission_ids
            consent.consent_type = Consent.CONSENT_TYPE_MANUAL_REVIEW
            consent.save()
            consent.build_request_policy()
            consent.save(update_fields=['odrl_request'])

            if set(permission_ids).issubset(preconsented_permission_ids):
                consent.approve(
                    permission_ids,
                    approval_path=Consent.CONSENT_TYPE_SUBJECT_PREFERENCE,
                )
                messages.success(request, 'This request matched the subject\'s sharing preferences and was approved automatically.')
            else:
                matched_count = len(set(permission_ids) & preconsented_permission_ids)
                if matched_count:
                    messages.info(request, f'{matched_count} requested permission(s) already match the subject\'s sharing preferences. The remaining permissions are waiting for review.')
                else:
                    messages.success(request, 'Consent request created and sent to the subject for review.')

            return redirect('consents:consent_details', consent_id=consent.id)
    else:
        form = ConsentRequestForm(requester=request.user)

    context = {
        'patient': patient,
        'form': form,
        'grouped_permissions': form.grouped_permissions,
        'selected_permission_ids': {str(value) for value in request.POST.getlist('permission_ids')},
        'preconsented_permission_ids': {str(item) for item in preconsented_permission_ids},
    }
    return render(request, 'consents/request_consent.html', context)


@login_required(login_url='users:login_view')
def review_pending_consents_view(request):
    # Show pending consents where user is either:
    # - The patient (subject) reviewing requests sent to them
    # - The data_processor (researcher/processor/regulator/agent) reviewing consent offered to them
    pending_consents = (
        Consent.objects
        .select_related('patient', 'data_processor', 'data_processor__role')
        .filter(
            Q(patient=request.user) |
            Q(data_processor=request.user) |
            Q(patient__delegated_to=request.user),
            status='pending'
        )
        .order_by('-created_date')
    )
    return render(request, 'consents/review_consents.html', {'pending_consents': pending_consents})


@login_required(login_url='users:login_view')
def approve_consent_view(request, consent_id):
    if request.method != 'POST':
        raise PermissionDenied('POST required.')

    consent = get_object_or_404(Consent.objects.select_related('patient', 'data_processor', 'data_processor__role'), pk=consent_id)
    if not _can_review(request.user, consent):
        raise PermissionDenied('You cannot approve this consent request.')

    if consent.status != 'pending':
        messages.info(request, 'Only pending requests can be reviewed.')
        return redirect('consents:consent_details', consent_id=consent.id)

    selected_permission_ids = [
        int(item)
        for item in request.POST.getlist('granted_permission_ids')
        if str(item).isdigit()
    ]

    if not selected_permission_ids and not request.POST.get('review_submitted'):
        selected_permission_ids = list(consent.requested_permissions)

    # Convert requested_permissions to integers for comparison (they are stored as strings)
    requested_perms_as_int = set(int(p) for p in consent.requested_permissions)
    selected_permission_ids = [
        permission_id
        for permission_id in selected_permission_ids
        if permission_id in requested_perms_as_int
    ]

    if selected_permission_ids:
        # Convert requested_permissions to integers for comparison
        requested_perms_as_int = set(int(p) for p in consent.requested_permissions)
        selected_perms_set = set(selected_permission_ids)

        if selected_perms_set == requested_perms_as_int:
            approval_path = Consent.CONSENT_TYPE_MANUAL_REVIEW
        else:
            approval_path = Consent.CONSENT_TYPE_PARTIAL_APPROVAL

        consent.approve(selected_permission_ids, approval_path=approval_path)
        if selected_perms_set == requested_perms_as_int:
            messages.success(request, 'Consent approved.')
        else:
            messages.success(request, 'Consent partially approved. Only the selected permissions were granted.')
    else:
        consent.reject(approval_path=Consent.CONSENT_TYPE_MANUAL_REVIEW)
        messages.warning(request, 'No permissions were selected, so the request was denied.')

    return redirect('consents:consent_details', consent_id=consent.id)


@login_required(login_url='users:login_view')
def reject_consent_view(request, consent_id):
    if request.method != 'POST':
        raise PermissionDenied('POST required.')

    consent = get_object_or_404(Consent.objects.select_related('patient', 'data_processor', 'data_processor__role'), pk=consent_id)
    if not _can_review(request.user, consent):
        raise PermissionDenied('You cannot reject this consent request.')

    consent.reject(approval_path=Consent.CONSENT_TYPE_MANUAL_REVIEW)
    messages.warning(request, 'Consent request denied.')
    return redirect('consents:consent_details', consent_id=consent.id)


@login_required(login_url='users:login_view')
def withdraw_consent_view(request, consent_id):
    if request.method != 'POST':
        raise PermissionDenied('POST required.')

    consent = get_object_or_404(Consent.objects.select_related('patient', 'data_processor'), pk=consent_id)
    if not _can_review(request.user, consent):
        raise PermissionDenied('You cannot withdraw this consent.')

    ok = consent.withdraw_consent()
    if ok:
        messages.warning(request, 'Consent withdrawn and linked policies were disabled.')
    else:
        messages.info(request, 'Only active consent can be withdrawn.')
    return redirect('consents:consent_details', consent_id=consent.id)


@login_required(login_url='users:login_view')
def subject_sharing_preferences_view(request, patient_id):
    patient = get_object_or_404(Patient.objects.select_related('user'), pk=patient_id)
    if not _can_manage_subject_preferences(request.user, patient):
        raise PermissionDenied('You cannot manage sharing preferences for this subject.')

    if request.method == 'POST':
        form = SubjectSharingPreferencesForm(request.POST, patient=patient)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sharing preferences updated. Future requests will be checked against these permissions automatically.')
            return redirect('patients:patient_medical_timeline', patient_id=patient.id)
    else:
        form = SubjectSharingPreferencesForm(patient=patient)

    selected_role_permission_ids = {str(value) for value in request.POST.getlist('role_permission_ids')} if request.method == 'POST' else {str(value) for value in form.initial.get('role_permission_ids', [])}

    return render(request, 'consents/subject_sharing_preferences.html', {
        'patient': patient,
        'form': form,
        'grouped_role_permissions': form.grouped_role_permissions,
        'selected_role_permission_ids': selected_role_permission_ids,
    })


@login_required(login_url='users:login_view')
def granted_records_view(request, consent_id):
    consent = get_object_or_404(
        Consent.objects.select_related('patient', 'data_processor', 'data_processor__role'),
        pk=consent_id,
    )

    if not _can_review(request.user, consent) and request.user.id != consent.data_processor_id:
        raise PermissionDenied('You cannot view the granted records for this consent.')

    readable_categories = {
        infer_data_category_from_permission(permission_name)
        for permission_name in (consent.granted_permissions or [])
        if infer_action_from_permission(permission_name) == 'read'
    }

    records_qs = (
        MedicalRecord.objects
        .select_related('patient', 'patient__user')
        .filter(patient__user=consent.patient)
        .order_by('-created_at')
    )

    if request.user.id == consent.data_processor_id and not _can_review(request.user, consent):
        records = [
            record
            for record in records_qs
            if record.data_category in readable_categories and check_access(request.user, record, 'read', purpose=consent.purpose)
        ]
    else:
        records = [record for record in records_qs if record.data_category in readable_categories]

    context = {
        'consent': consent,
        'records': records,
        'readable_categories': sorted(readable_categories),
    }
    return render(request, 'consents/granted_records.html', context)


@login_required(login_url='users:login_view')
def consent_details(request, consent_id):
    consent = get_object_or_404(
        Consent.objects.select_related('patient', 'data_processor', 'data_processor__role'),
        pk=consent_id,
    )

    # Allow view if: can review OR is data processor OR is patient (own consent)
    can_view = _can_review(request.user, consent) or request.user.id == consent.data_processor_id or request.user.id == consent.patient_id
    if not can_view:
        raise PermissionDenied('You cannot view this consent.')

    patient_profile = get_object_or_404(Patient.objects.select_related('user'), user=consent.patient)
    requested_permissions = consent.requested_permission_objects
    granted_permissions = consent.granted_permission_objects
    subject_preconsented_ids = _subject_preconsented_permission_ids(patient_profile, consent.data_processor.role)
    granted_permission_names = set(consent.granted_permissions or [])

    permission_rows = []
    for permission in requested_permissions:
        permission_rows.append({
            'id': permission.id,
            'name': permission.name,
            'label': prettify_permission(permission.name),
            'preconsented': permission.id in subject_preconsented_ids,
            'granted': permission.name in granted_permission_names,
            'denied': consent.status in {'active', 'denied'} and permission.name not in granted_permission_names,
        })

    context = {
        'consent': consent,
        'requested_permissions': requested_permissions,
        'granted_permissions': granted_permissions,
        'permission_rows': permission_rows,
        'subject_preconsented_ids': subject_preconsented_ids,
        'can_review': _can_review(request.user, consent),
        'can_view_granted_records': consent.status == 'active' and bool(consent.granted_permissions),
        'odrl_request_pretty': json.dumps(consent.odrl_request or {}, ensure_ascii=False, indent=2),
        'odrl_policy_pretty': json.dumps(consent.odrl_policy or {}, ensure_ascii=False, indent=2),
    }
    return render(request, 'consents/consent_details.html', context)
