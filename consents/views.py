from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from services.anonymise import ROLE_PRIVACY_RULES, anonymize_postcodes, transform_patient_data
from .models import *
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from consents.forms import (
    ALLOWED_REQUESTER_ROLES,
    ConsentRequestForm,
    OrganizationConsentRequestForm,
    SubjectSharingPreferencesForm,
)
from consents.models import Consent
from patients.models import MedicalRecord, Patient, PatientPermission
from users.models import CustomPermission
from services.odrl import infer_action_from_permission, infer_data_category_from_permission, prettify_permission
from services.policy_engine import check_access, evaluate_access
import csv
from django.http import HttpResponse
from django.utils import timezone



def _can_request(user):
    return user.is_authenticated and getattr(getattr(user, 'role', None), 'name', None) in ALLOWED_REQUESTER_ROLES



def _can_review(user, consent):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if consent.patient_id == user.id:
        return True
    if consent.patient.delegated_to_id == user.id:
        return True
    return False



def _can_manage_subject_preferences(user, patient):
    """Only the data subject can manage their own sharing preferences."""
    if not user.is_authenticated:
        return False

    role_name = getattr(getattr(user, 'role', None), 'name', None)
    return role_name == 'subject' and patient.user_id == user.id



def _subject_preconsented_permission_ids(patient, role):
    return set(
        PatientPermission.objects
        .filter(patient=patient, role_permission__role=role)
        .values_list('role_permission__permission_id', flat=True)
    )



def _create_consent_request(patient, requester, cleaned_data, permission_ids, permissions, categories):
    """Create one consent request and auto-approve it when the subject pre-consented."""
    consent = Consent.objects.create(
        patient=patient.user,
        data_processor=requester,
        data_type=', '.join(categories),
        purpose=cleaned_data['purpose'],
        expiry_date=cleaned_data.get('expiry_date'),
        notes=cleaned_data.get('notes') or '',
        requested_permissions=permission_ids,
        consent_type=Consent.CONSENT_TYPE_MANUAL_REVIEW,
    )
    consent.build_request_policy()
    consent.save(update_fields=['odrl_request'])

    preconsented_permission_ids = _subject_preconsented_permission_ids(patient, requester.role)
    requested_permission_id_set = set(permission_ids)
    matched_count = len(requested_permission_id_set & preconsented_permission_ids)

    auto_approved = False
    if requested_permission_id_set and requested_permission_id_set.issubset(preconsented_permission_ids):
        consent.approve(
            permission_ids,
            approval_path=Consent.CONSENT_TYPE_SUBJECT_PREFERENCE,
        )
        auto_approved = True

    return consent, auto_approved, matched_count


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

            consent, auto_approved, matched_count = _create_consent_request(
                patient=patient,
                requester=request.user,
                cleaned_data=form.cleaned_data,
                permission_ids=permission_ids,
                permissions=permissions,
                categories=categories,
            )

            if auto_approved:
                messages.success(request, 'This request matched the subject\'s sharing preferences and was approved automatically.')
            elif matched_count:
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
def request_organization_consent_view(request):
    if not _can_request(request.user):
        raise PermissionDenied('Your role cannot request consent.')

    initial_organization = (
        request.GET.get('organization_name')
        or request.GET.get('organization')
        or ''
    )

    if request.method == 'POST':
        form = OrganizationConsentRequestForm(request.POST, requester=request.user)
        if form.is_valid():
            organization_name = form.cleaned_data['organization_name']
            permission_ids = form.cleaned_data['permission_ids']
            permissions = list(CustomPermission.objects.filter(id__in=permission_ids))
            categories = sorted({infer_data_category_from_permission(perm.name) for perm in permissions})
            patients = list(
                Patient.objects
                .select_related('user')
                .filter(user__organization_name=organization_name)
                .order_by('user__last_name', 'user__first_name', 'id')
            )

            created_count = 0
            auto_approved_count = 0
            pending_count = 0
            partial_preference_count = 0

            with transaction.atomic():
                for patient in patients:
                    _, auto_approved, matched_count = _create_consent_request(
                        patient=patient,
                        requester=request.user,
                        cleaned_data=form.cleaned_data,
                        permission_ids=permission_ids,
                        permissions=permissions,
                        categories=categories,
                    )
                    created_count += 1
                    if auto_approved:
                        auto_approved_count += 1
                    else:
                        pending_count += 1
                        if matched_count:
                            partial_preference_count += 1

            messages.success(
                request,
                (
                    f'Created {created_count} consent request(s) for organisation "{organization_name}". '
                    f'{auto_approved_count} auto-approved, {pending_count} waiting for subject review.'
                ),
            )
            if partial_preference_count:
                messages.info(
                    request,
                    f'{partial_preference_count} pending request(s) had some permissions already covered by subject sharing preferences.'
                )
            return redirect('pages:consent_records')
    else:
        form = OrganizationConsentRequestForm(
            requester=request.user,
            initial={'organization_name': initial_organization},
        )

    selected_organization = (
        request.POST.get('organization_name')
        if request.method == 'POST'
        else initial_organization
    )
    organization_subject_count = 0
    if selected_organization:
        organization_subject_count = Patient.objects.filter(user__organization_name=selected_organization).count()

    context = {
        'form': form,
        'grouped_permissions': form.grouped_permissions,
        'selected_permission_ids': {str(value) for value in request.POST.getlist('permission_ids')},
        'selected_organization': selected_organization,
        'organization_subject_count': organization_subject_count,
    }
    return render(request, 'consents/request_organization_consent.html', context)


@login_required(login_url='users:login_view')
def review_pending_consents_view(request):
    pending_consents = (
        Consent.objects
        .select_related('patient', 'data_processor', 'data_processor__role')
        .filter(Q(patient=request.user) | Q(patient__delegated_to=request.user), status='pending')
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

    selected_permission_ids = [
        permission_id
        for permission_id in selected_permission_ids
        if permission_id in set(consent.requested_permissions)
    ]

    if selected_permission_ids:
        if set(selected_permission_ids) == set(consent.requested_permissions):
            approval_path = Consent.CONSENT_TYPE_MANUAL_REVIEW
        else:
            approval_path = Consent.CONSENT_TYPE_PARTIAL_APPROVAL

        consent.approve(selected_permission_ids, approval_path=approval_path)
        if set(selected_permission_ids) == set(consent.requested_permissions):
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


def _render_subject_sharing_preferences(request, patient, redirect_to='patients:patient_medical_timeline'):
    if not _can_manage_subject_preferences(request.user, patient):
        raise PermissionDenied('Only the subject can manage their own sharing preferences.')

    if request.method == 'POST':
        form = SubjectSharingPreferencesForm(request.POST, patient=patient)
        if form.is_valid():
            form.save()
            messages.success(request, 'Sharing preferences updated. Future requests will be checked against these permissions automatically.')
            if redirect_to == 'pages:my_data':
                return redirect('pages:my_data')
            return redirect('patients:patient_medical_timeline', patient_id=patient.id)
    else:
        form = SubjectSharingPreferencesForm(patient=patient)

    selected_role_permission_ids = (
        {str(value) for value in request.POST.getlist('role_permission_ids')}
        if request.method == 'POST'
        else {str(value) for value in form.initial.get('role_permission_ids', [])}
    )

    return render(request, 'consents/subject_sharing_preferences.html', {
        'patient': patient,
        'form': form,
        'grouped_role_permissions': form.grouped_role_permissions,
        'selected_role_permission_ids': selected_role_permission_ids,
        'is_own_preferences': redirect_to == 'pages:my_data',
    })


@login_required(login_url='users:login_view')
def my_subject_sharing_preferences_view(request):
    role_name = getattr(getattr(request.user, 'role', None), 'name', None)
    if role_name != 'subject':
        raise PermissionDenied('Only subjects can manage sharing preferences.')

    patient = Patient.objects.select_related('user').filter(user=request.user).first()
    if not patient:
        messages.error(request, 'No subject profile was found for your account yet.')
        return redirect('pages:my_data')

    return _render_subject_sharing_preferences(request, patient, redirect_to='pages:my_data')


@login_required(login_url='users:login_view')
def subject_sharing_preferences_view(request, patient_id):
    patient = get_object_or_404(Patient.objects.select_related('user'), pk=patient_id)
    return _render_subject_sharing_preferences(request, patient)


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

    if not _can_review(request.user, consent) and request.user.id != consent.data_processor_id:
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


def download_allowed_data_csv(request):

    requestor = request.GET.get('requestor')
    requestor_user_acc = User.objects.get(id=requestor)

    datatype = request.GET.get('datatype')
    purpose = request.GET.get('purpose')

    patient_csv_data = []

    role = requestor_user_acc.role.name
    privacy_rules = ROLE_PRIVACY_RULES.get(role)
    if not privacy_rules:
        return HttpResponse(
            "No privacy rules configured for this role.",
            status=400
        )

    allowed_patients = []

    for patient in Patient.objects.all():

        log = evaluate_access(
            requester=requestor_user_acc,
            patient=patient,
            resource_type=datatype,
            purpose=purpose,
            action='read',
        )

        if log.decision == "allow":
            allowed_patients.append((patient, log))

    patients_only = [p for p, _ in allowed_patients]

    anonymized_postcodes = anonymize_postcodes(
        patients_only,
        k=privacy_rules["k_anonymity"]
    )

    for patient, log in allowed_patients:

        transformed = transform_patient_data(
            patient,
            log,
            privacy_rules,
            anonymized_postcodes
        )

        patient_csv_data.append(transformed)

    filename = (
        f"Patient_Data_"
        f"{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    )

    response = HttpResponse(content_type='text/csv')

    response['Content-Disposition'] = (
        f'attachment; filename="{filename}"'
    )

    writer = csv.writer(response)

    if patient_csv_data:

        headers = list(patient_csv_data[0].keys())

        writer.writerow(headers)

        for row in patient_csv_data:
            writer.writerow([
                row.get(header, "")
                for header in headers
            ])

    else:

        writer.writerow(["No data available"])

    return response