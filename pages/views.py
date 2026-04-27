from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count
from django.shortcuts import render
from django.shortcuts import render, redirect

from consents.models import Consent
from patients.models import MedicalRecord, Patient
from users.models import User, Role, CustomPermission
from services.odrl import infer_data_category_from_permission


@login_required(login_url='users:login_view')
def home(request):
    return render(request, 'pages/home.html')


@login_required(login_url='users:login_view')
def data_subjects(request):
    # Get current user's role
    user_role = getattr(getattr(request.user, 'role', None), 'name', None)

    # Build query with annotation for active consents count for current user's role
    from django.db.models import Count, Q, OuterRef, Subquery
    from consents.models import Consent

    # Annotate with count of active consents where data_processor has the same role as current user
    data_subjects_list = Patient.objects.select_related('user').annotate(
        active_consents_count=Subquery(
            Consent.objects.filter(
                patient=OuterRef('user'),
                data_processor__role=request.user.role,
                status='active'
            ).values('patient').annotate(c=Count('id')).values('c')[:1]
        )
    ).order_by('id')

    paginator = Paginator(data_subjects_list, 6)
    page = request.GET.get('page')
    try:
        data_subjects_list = paginator.page(page)
    except PageNotAnInteger:
        data_subjects_list = paginator.page(1)
    except EmptyPage:
        data_subjects_list = paginator.page(paginator.num_pages)

    return render(request, 'pages/data_subjects.html', {'data_subjects_list': data_subjects_list})


@login_required(login_url='users:login_view')
def consent_records(request):
    from users.models import User, Role, CustomPermission
    from patients.models import RolePermission

    consent_list = Consent.objects.select_related('patient', 'data_processor')

    user_role = getattr(getattr(request.user, 'role', None), 'name', None)
    is_subject = (user_role == 'subject')

    if request.user.is_staff or request.user.is_superuser:
        consent_list = consent_list.all()
    elif user_role == 'subject':
        consent_list = consent_list.filter(patient=request.user)
    else:
        consent_list = consent_list.filter(data_processor=request.user)

    consent_list = consent_list.order_by('-id')
    paginator = Paginator(consent_list, 6)
    page = request.GET.get('page')

    # Handle grant consent form (Subject only)
    grant_form = None
    available_users = []
    all_role_permissions = {}

    if is_subject:
        # Get users of allowed roles (excluding subject)
        allowed_roles = Role.objects.exclude(name='subject')
        available_users = User.objects.filter(
            role__in=allowed_roles,
            is_active=True
        ).select_related('role').order_by('username')

        # Get permissions grouped by role
        for role in allowed_roles:
            perms = RolePermission.objects.filter(role=role).select_related('permission')
            perm_list = []
            for rp in perms:
                perm_list.append({
                    'id': rp.permission.id,
                    'name': rp.permission.name,
                })
            all_role_permissions[role.name] = perm_list

        if request.method == 'POST' and 'grant_consent' in request.POST:
            selected_user_id = request.POST.get('data_processor_id')
            purpose = request.POST.get('purpose', '')
            expiry_date = request.POST.get('expiry_date') or None
            notes = request.POST.get('notes', '')
            permission_ids = request.POST.getlist('permission_ids')

            if not selected_user_id:
                messages.error(request, 'Please select a data processor.')
            elif not permission_ids:
                messages.error(request, 'Please select at least one permission.')
            else:
                selected_user = User.objects.get(id=selected_user_id)
                selected_role = selected_user.role

                # Validate permissions match the selected user's role
                allowed_perm_ids = set(
                    rp.permission_id for rp in RolePermission.objects.filter(role=selected_role)
                )
                # Convert permission_ids to integers for comparison
                selected_perm_ids = set(int(pid) for pid in permission_ids)
                invalid_perms = selected_perm_ids - allowed_perm_ids
                if invalid_perms:
                    messages.error(request, 'Invalid permissions selected for this role.')
                else:
                    # Create consent as pending
                    from datetime import datetime
                    permissions = list(CustomPermission.objects.filter(id__in=permission_ids))
                    categories = sorted({infer_data_category_from_permission(perm.name) for perm in permissions})

                    # Convert expiry_date string to date object if provided
                    expiry_date_obj = None
                    if expiry_date:
                        try:
                            expiry_date_obj = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                        except ValueError:
                            pass

                    consent = Consent.objects.create(
                        patient=request.user,
                        data_processor=selected_user,
                        purpose=purpose,
                        expiry_date=expiry_date_obj,
                        notes=notes,
                        data_type=', '.join(categories),
                        requested_permissions=permission_ids,
                        status='pending',
                        consent_type='GRANTED_BY_SUBJECT',
                    )
                    consent.build_request_policy()
                    consent.save(update_fields=['odrl_request'])

                    messages.success(request, f'Consent request sent to {selected_user.get_full_name()}. They need to accept it.')
                    return redirect('pages:consent_records')

    try:
        consents = paginator.page(page)
    except PageNotAnInteger:
        consents = paginator.page(1)
    except EmptyPage:
        consents = paginator.page(paginator.num_pages)

    context = {
        'consents': consents,
        'is_paginated': True,
        'page_obj': consents,
        'paginator': paginator,
        'grant_form': grant_form,
        'available_users': available_users,
        'all_role_permissions': all_role_permissions,
    }
    return render(request, 'pages/consent_records.html', context)


@login_required(login_url='users:login_view')
def policies(request):
    return render(request, 'pages/policies.html')


@login_required(login_url='users:login_view')
def dashboard_view(request):
    all_consents = Consent.objects.all()
    context = {
        'consent_total': all_consents.count(),
        'consent_active': all_consents.filter(status='active').count(),
        'consent_pending': all_consents.filter(status='pending').count(),
        'consent_withdrawn': all_consents.filter(status='withdrawn').count(),
        'recent_consents': all_consents.select_related('patient', 'data_processor')[:5],
        'recent_patients': Patient.objects.select_related('user').order_by('-id')[:5],
    }

    # Add patient_id for subject role to access their medical records
    role = getattr(getattr(request.user, 'role', None), 'name', None)
    if role == 'subject':
        try:
            patient = Patient.objects.get(user=request.user)
            context['patient_id'] = patient.id
        except Patient.DoesNotExist:
            pass

    return render(request, 'pages/dashboard.html', context)


@login_required(login_url='users:login_view')
def medical_records(request):
    all_records = MedicalRecord.objects.select_related('patient', 'patient__user').order_by('-created_at')
    paginator = Paginator(all_records, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    category_counts = MedicalRecord.objects.values('data_category').annotate(count=Count('data_category'))
    category_counts_dict = {
        dict(MedicalRecord.DATA_CATEGORY_CHOICES).get(item['data_category'], item['data_category']): item['count']
        for item in category_counts
    }

    context = {
        'medical_records': page_obj,
        'category_counts': category_counts_dict,
    }
    return render(request, 'pages/medical_records.html', context)





from django.contrib import messages
from consents.models import AccessRequest, DecisionLog
from services.policy_engine import evaluate_access
from services.compliance_checker import check_violations


@login_required(login_url='users:login_view')
def access_request_view(request):
    patients = Patient.objects.select_related('user').all()
    mode = request.GET.get('mode', 'single')
    batch_mode = (mode == 'batch')

    # Get authorized records for researcher
    role_name = getattr(getattr(request.user, 'role', None), 'name', None)
    authorized_records = []
    if role_name == 'researcher':
        from consents.models import ConsentPolicy
        from patients.models import MedicalRecord

        # Get all active consent policies for this researcher
        policies = ConsentPolicy.objects.filter(
            role=request.user.role,
            active=True
        ).select_related('patient', 'patient__user', 'permission')

        # Get records that match these policies
        policy_data = {}
        for p in policies:
            patient_id = p.patient_id
            data_category = p.data_category
            if patient_id not in policy_data:
                policy_data[patient_id] = set()
            policy_data[patient_id].add(data_category)

        # Query medical records
        for patient_id, categories in policy_data.items():
            records = MedicalRecord.objects.filter(
                patient_id=patient_id,
                data_category__in=categories
            ).select_related('patient', 'patient__user')
            for record in records:
                authorized_records.append({
                    'patient_name': f"{record.patient.user.first_name} {record.patient.user.last_name}",
                    'patient_id': record.patient_id,
                    'title': record.title,
                    'category': record.data_category,
                    'created_at': record.created_at,
                })

    context = {
        'patients': patients,
        'batch_mode': batch_mode,
        'authorized_records': authorized_records,
    }

    if request.method == 'POST':
        post_mode = request.POST.get('mode', 'single')

        # Single request
        if post_mode == 'single':
            patient_id    = request.POST.get('patient_id')
            resource_type = request.POST.get('resource_type')
            purpose       = request.POST.get('purpose')
            action        = request.POST.get('action', 'read')
            try:
                patient = Patient.objects.get(id=patient_id)
                log = evaluate_access(
                    requester=request.user,
                    patient=patient,
                    resource_type=resource_type,
                    purpose=purpose,
                    action=action,
                )
                context.update({
                    'result':    log,
                    'decision':  log.decision,
                    'reason':    log.reason,
                    'submitted': True,
                    'batch_mode': False,
                })
            except Patient.DoesNotExist:
                messages.error(request, 'Patient not found.')

        # Batch search
        elif post_mode == 'batch_search':
            resource_type = request.POST.get('resource_type')
            purpose       = request.POST.get('purpose')
            matched_patients = Patient.objects.filter(
                medicalrecord__data_category=resource_type,
                medicalrecord__record_status='active',
            ).select_related('user').distinct()
            context.update({
                'batch_mode':            True,
                'matched_patients':      matched_patients,
                'selected_resource_type': resource_type,
                'batch_purpose':         purpose,
            })

        # Batch submit
        elif post_mode == 'batch_submit':
            patient_ids   = request.POST.getlist('patient_ids')
            resource_type = request.POST.get('resource_type')
            purpose       = request.POST.get('purpose')
            batch_results = []
            for pid in patient_ids:
                try:
                    patient = Patient.objects.get(id=pid)
                    log = evaluate_access(
                        requester=request.user,
                        patient=patient,
                        resource_type=resource_type,
                        purpose=purpose,
                        action='read',
                    )
                    batch_results.append({
                        'patient':           str(patient),
                        'decision':          log.decision,
                        'reason':            log.reason,
                        'compliance_status': log.compliance_status,
                    })
                except Patient.DoesNotExist:
                    continue
            context.update({
                'batch_mode':    True,
                'batch_results': batch_results,
            })

    return render(request, 'pages/access_request.html', context)


@login_required(login_url='users:login_view')
def compliance_dashboard_view(request):
    patients = Patient.objects.select_related('user').all()
    selected_patient = None
    report = None

    patient_id = request.GET.get('patient_id')
    if patient_id:
        try:
            selected_patient = Patient.objects.get(id=patient_id)
            report = check_violations(selected_patient)
        except Patient.DoesNotExist:
            messages.error(request, 'Patient not found.')

    recent_logs = DecisionLog.objects.select_related(
        'access_request',
        'access_request__requester',
        'access_request__patient',
    ).order_by('-checked_at')[:20]

    context = {
        'patients':         patients,
        'selected_patient': selected_patient,
        'report':           report,
        'recent_logs':      recent_logs,
    }
    return render(request, 'pages/compliance_dashboard.html', context)




@login_required(login_url='users:login_view')
def my_data_view(request):
    # Only for subject role
    role = getattr(getattr(request.user, 'role', None), 'name', None)
    if role != 'subject':
        messages.error(request, 'This page is only accessible to patients.')
        return redirect('pages:dashboard_view')

    # Get patient profile
    try:
        patient = Patient.objects.get(user=request.user)
    except Patient.DoesNotExist:
        messages.error(request, 'Patient profile not found.')
        return redirect('pages:dashboard_view')

    # Who accessed my data
    access_logs = DecisionLog.objects.filter(
        access_request__patient=patient
    ).select_related(
        'access_request',
        'access_request__requester',
        'access_request__requester__role',
        'matched_consent',
    ).order_by('-checked_at')

    # My active consents
    my_consents = Consent.objects.filter(
        patient=request.user
    ).order_by('-created_date')

    context = {
        'patient':     patient,
        'patient_id': patient.id,  # For navbar links
        'access_logs': access_logs,
        'my_consents': my_consents,
        'allow_count':   access_logs.filter(decision='allow').count(),
        'deny_count':    access_logs.filter(decision='deny').count(),
        'redact_count':  access_logs.filter(decision='limited').count(),
    }
    return render(request, 'pages/my_data.html', context)