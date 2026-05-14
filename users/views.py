from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password

from django.contrib.auth import get_user_model
from .models import Role, CustomPermission, RolePermission, Delegation, DelegationLog, DelegationActivation
from .forms import SignupForm, LoginForm, ProfileForm, ChangePasswordForm, DelegateForm
from .utils import authenticate
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

# Import processor activation view
from .views_activation import activation_requests_view

User = get_user_model()


# ─────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────

def _create_patient(user):
    from patients.models import Patient
    Patient.objects.get_or_create(user=user)


# ─────────────────────────────────────────────
# auth views
# ─────────────────────────────────────────────

def send_welcome_email(user):
    subject = 'Welcome to The Consent Management System'
    text_content = f'Hi {user.username}, thanks for signing up. You will receive an email to confirm that you are able to log in to the system after your verification process is completed.'
    html_content = render_to_string('emails/await_verification.html', {'user': user})

    email = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email]
    )
    email.attach_alternative(html_content, 'text/html')
    email.send()

def send_verification_email(user):
    subject = 'Account Verification'
    text_content = f'Hi {user.username}, thanks for signing up. Your account has been verified and you can now log in.'
    html_content = render_to_string('emails/verification.html', {'user': user})

    email = EmailMultiAlternatives(
        subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email]
    )
    email.attach_alternative(html_content, 'text/html')
    email.send()

def signup_view(request):
    form = SignupForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            cd = form.cleaned_data
            user = User(
                first_name=cd["first_name"],
                last_name=cd["last_name"],
                email=cd["email"].lower(),
                organization_name=cd.get("organisation", ""),
                role=cd["role"],
            )
            if hasattr(User, "username"):
                user.username = cd["email"].lower()
            user.password = make_password(cd["password1"])
            user.save()



            if cd["role"].name == "subject":
                _create_patient(user)
            else:
                try:
                    user.is_active = False
                    user.save()
                    send_welcome_email(user)
                except Exception as e:
                    # Log the error or handle it as needed
                    print(f"Error sending welcome email: {e}")

            messages.success(request, "Account created successfully. You can now log in.")
            return redirect("users:login_view")
        else:
            # surface form errors as Django messages so the existing toast template picks them up
            for field, errors in form.errors.items():
                for error in errors:
                    label = form.fields[field].label if field != "__all__" else ""
                    messages.error(request, f"{label}: {error}" if label else error)

    roles = Role.objects.all()
    return render(request, "users/signup.html", {"form": form, "roles": roles})


def login_view(request):
    form = LoginForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            cd = form.cleaned_data
            user = authenticate(password=cd["password"], username=cd["username"])
            if user is not None:
                login(request, user)
                messages.success(request, "Logged in successfully.")
                next_url = request.GET.get("next", "pages:home")
                return redirect(next_url)
            else:
                messages.error(request, "Invalid email or password.", extra_tags="danger")
        else:
            messages.error(request, "Please correct the errors below.", extra_tags="danger")

    return render(request, "users/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect("users:login_view")


# ─────────────────────────────────────────────
# profile views
# ─────────────────────────────────────────────

@login_required(login_url="users:login_view")
def profile_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("users:profile_view")
        else:
            messages.error(request, "Please correct the errors below.", extra_tags="danger")

    return render(request, "users/profile.html", {"form": form})


@login_required(login_url="users:login_view")
def change_password_view(request):
    form = ChangePasswordForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            cd = form.cleaned_data
            if not request.user.check_password(cd["current_password"]):
                form.add_error("current_password", "Current password is incorrect.")
                messages.error(request, "Current password is incorrect.", extra_tags="danger")
            else:
                request.user.set_password(cd["new_password"])
                request.user.save()
                # re-login so session stays valid after password change
                login(request, request.user)
                messages.success(request, "Password changed successfully.")
                return redirect("users:profile_view")

    return render(request, "users/change_password.html", {"form": form})


@login_required(login_url="users:login_view")
def delegation_view(request):
    """Data subject delegation management page."""
    # Check: only subject role can access
    user_role = getattr(getattr(request.user, 'role', None), 'name', None)
    if user_role != 'subject':
        messages.error(request, 'Only data subjects can access this page.', extra_tags='danger')
        return redirect('pages:home')

    # Get current delegation
    current_delegation = Delegation.objects.filter(
        data_subject=request.user,
        status__in=['pending', 'accepted', 'active']
    ).order_by('-created_at').first()

    candidates = []
    search_query = ''

    if request.method == 'POST':
        action = request.POST.get('action')

        # === Search ===
        if action == 'search':
            search_query = request.POST.get('query', '').strip()
            candidates = []
            if search_query:
                candidates = list(User.objects.filter(
                    role__name='subject',
                    is_active=True
                ).exclude(
                    id=request.user.id
                ).filter(
                    Q(username__icontains=search_query) |
                    Q(first_name__icontains=search_query) |
                    Q(last_name__icontains=search_query) |
                    Q(email__icontains=search_query)
                ).distinct()[:20])

            return render(request, 'users/delegation.html', {
                'current_delegation': current_delegation,
                'candidates': candidates,
                'search_query': search_query,
            })

        # === Create/Replace ===
        if action in ('create', 'replace'):
            proxy_id = request.POST.get('proxy_id')

            # Check 1: cannot delegate to self
            if str(proxy_id) == str(request.user.id):
                messages.error(request, 'You cannot delegate to yourself.', extra_tags='danger')
                return redirect('users:delegation_view')

            # Check 2: proxy must be another subject
            proxy = User.objects.filter(
                id=proxy_id,
                role__name='subject',
                is_active=True
            ).first()

            if not proxy:
                messages.error(request, 'Please select a valid proxy.', extra_tags='danger')
                return redirect('users:delegation_view')

            if action == 'replace' and current_delegation:
                # Mark old delegation as revoked
                old_proxy_name = current_delegation.proxy.get_full_name()
                current_delegation.status = 'revoked'
                current_delegation.revoked_at = timezone.now()
                current_delegation.save(update_fields=['status', 'revoked_at'])

                new_proxy_name = proxy.get_full_name()
                DelegationLog.objects.create(
                    delegation=current_delegation,
                    action='replaced',
                    performed_by=request.user,
                    notes=f'{old_proxy_name} -> {new_proxy_name}'
                )

            # Create new delegation
            new_delegation = Delegation.objects.create(
                data_subject=request.user,
                proxy=proxy,
                status='pending'
            )

            DelegationLog.objects.create(
                delegation=new_delegation,
                action='created',
                performed_by=request.user,
                notes=f'Delegated to {proxy.get_full_name()}'
            )

            messages.success(request, 'Proxy set. Pending activation.')
            return redirect('users:delegation_view')

        # === Revoke ===
        if action == 'revoke' and current_delegation:
            current_delegation.status = 'revoked'
            current_delegation.revoked_at = timezone.now()
            current_delegation.save(update_fields=['status', 'revoked_at'])

            DelegationLog.objects.create(
                delegation=current_delegation,
                action='revoked',
                performed_by=request.user
            )

            messages.success(request, 'Delegation revoked.')
            return redirect('users:delegation_view')

        # === Deactivate (only for active delegation) ===
        if action == 'deactivate' and current_delegation and current_delegation.status == 'active':
            current_delegation.status = 'accepted'
            current_delegation.save(update_fields=['status'])

            DelegationLog.objects.create(
                delegation=current_delegation,
                action='deactivated',
                performed_by=request.user,
                notes=f'Deactivated delegation to {current_delegation.proxy.get_full_name()}'
            )

            messages.success(request, 'Delegation deactivated. You can reactivate later if needed.')
            return redirect('users:delegation_view')

    # Get delegation operation history
    delegation_logs = DelegationLog.objects.filter(
        delegation__data_subject=request.user
    ).select_related('delegation', 'performed_by')[:50]

    return render(request, 'users/delegation.html', {
        'current_delegation': current_delegation,
        'delegation_logs': delegation_logs,
    })


@login_required(login_url="users:login_view")
def delegate_requests_view(request):
    """My Delegation Requests - Accept/Reject delegate requests and view accepted delegations."""
    # Check: only subject role can access (delegate B has role='subject')
    user_role = getattr(getattr(request.user, 'role', None), 'name', None)
    if user_role != 'subject':
        messages.error(request, 'Only data subjects can access this page.', extra_tags='danger')
        return redirect('pages:home')

    # First section: pending delegate requests
    pending_delegations = Delegation.objects.filter(
        proxy=request.user,
        status='pending'
    ).select_related('data_subject')

    # Second section: accepted but not yet active
    accepted_delegations = Delegation.objects.filter(
        proxy=request.user,
        status='accepted'
    ).select_related('data_subject')

    # Get pending activations to mark which delegations already have pending requests
    pending_activations = DelegationActivation.objects.filter(
        status='pending'
    ).values_list('delegation_id', flat=True)

    # Third section: pending activation requests from doctor/processor that this delegate B can process
    # B can process requests where:
    # - status = pending
    # - delegation.proxy = current user (B)
    # - initiated_by != current user (not own request)
    pending_activation_requests = DelegationActivation.objects.filter(
        status='pending',
        delegation__proxy=request.user
    ).exclude(
        initiated_by=request.user
    ).select_related('delegation__data_subject', 'initiated_by')

    # Fourth section: delegate role history (as proxy)
    delegate_role_logs = DelegationLog.objects.filter(
        delegation__proxy=request.user
    ).select_related('delegation', 'performed_by')[:50]

    if request.method == 'POST':
        action = request.POST.get('action')
        delegation_id = request.POST.get('delegation_id')
        activation_id = request.POST.get('activation_id')

        # Skip delegation check for activation confirm/reject actions
        if action not in ('confirm_activation', 'reject_activation'):
            # Get delegation - must belong to this proxy and have correct status
            delegation = None
            if action in ('accept', 'reject'):
                delegation = Delegation.objects.filter(
                    id=delegation_id,
                    proxy=request.user,
                    status='pending'
                ).first()
            elif action == 'request_activation':
                delegation = Delegation.objects.filter(
                    id=delegation_id,
                    proxy=request.user,
                    status='accepted'
                ).first()

            if not delegation:
                messages.error(request, 'Invalid request.', extra_tags='danger')
                return redirect('users:delegate_requests_view')

        if action == 'accept':
            delegation.status = 'accepted'
            delegation.save(update_fields=['status'])
            DelegationLog.objects.create(
                delegation=delegation,
                action='accepted',
                performed_by=request.user,
                notes=f'Accepted delegation from {delegation.data_subject.get_full_name()}'
            )
            messages.success(request, 'Delegation accepted. You can act on their behalf when activated.')

        elif action == 'reject':
            delegation.status = 'rejected'
            delegation.save(update_fields=['status'])
            DelegationLog.objects.create(
                delegation=delegation,
                action='rejected',
                performed_by=request.user,
                notes=f'Rejected delegation from {delegation.data_subject.get_full_name()}'
            )
            messages.success(request, 'Delegation rejected.')

        elif action == 'request_activation':
            # Delegate B requests activation for accepted delegation
            reason = request.POST.get('reason', '').strip()

            if not reason:
                messages.error(request, 'Please provide a reason for activation.', extra_tags='danger')
                return redirect('users:delegate_requests_view')

            # Check: already has pending activation?
            existing = DelegationActivation.objects.filter(
                delegation=delegation,
                status='pending'
            ).first()
            if existing:
                messages.error(request, 'An activation request is already pending for this delegation.', extra_tags='danger')
                return redirect('users:delegate_requests_view')

            # Create activation request
            DelegationActivation.objects.create(
                delegation=delegation,
                initiated_by=request.user,
                reason=reason,
                status='pending'
            )

            # Log action
            DelegationLog.objects.create(
                delegation=delegation,
                action='activation_requested',
                performed_by=request.user,
                notes=reason
            )

            messages.success(request, 'Activation request submitted.')

        elif action in ('confirm_activation', 'reject_activation'):
            # Delegate B confirms/rejects activation request from doctor/processor
            activation = DelegationActivation.objects.filter(
                id=activation_id,
                status='pending',
                delegation__proxy=request.user
            ).select_related('delegation').first()

            if not activation:
                messages.error(request, 'Invalid activation request.', extra_tags='danger')
                return redirect('users:delegate_requests_view')

            # Check: cannot process own request
            if activation.initiated_by == request.user:
                messages.error(request, 'You cannot process your own activation request.', extra_tags='danger')
                return redirect('users:delegate_requests_view')

            # Check: delegation still in accepted status
            if activation.delegation.status != 'accepted':
                messages.error(request, 'Delegation is no longer in accepted status.', extra_tags='danger')
                return redirect('users:delegate_requests_view')

            if action == 'confirm_activation':
                with transaction.atomic():
                    # Update delegation
                    activation.delegation.status = 'active'
                    activation.delegation.activated_at = timezone.now()
                    activation.delegation.save(update_fields=['status', 'activated_at'])

                    # Update activation
                    activation.status = 'confirmed'
                    activation.confirmed_by = request.user
                    activation.confirmed_at = timezone.now()
                    activation.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

                    # Log action
                    DelegationLog.objects.create(
                        delegation=activation.delegation,
                        action='activation_confirmed',
                        performed_by=request.user,
                        notes=f'Activation confirmed for {activation.delegation.data_subject.get_full_name()}'
                    )

                messages.success(request, 'Delegation activated successfully. You can now act on their behalf.')

            elif action == 'reject_activation':
                # Reject activation request
                activation.status = 'rejected'
                activation.confirmed_by = request.user
                activation.confirmed_at = timezone.now()
                activation.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

                # Log action
                DelegationLog.objects.create(
                    delegation=activation.delegation,
                    action='activation_rejected',
                    performed_by=request.user,
                    notes='Activation request rejected'
                )

                messages.success(request, 'Activation request rejected.')

        return redirect('users:delegate_requests_view')

    return render(request, 'users/delegate_requests.html', {
        'pending_delegations': pending_delegations,
        'accepted_delegations': accepted_delegations,
        'pending_activations': list(pending_activations),
        'pending_activation_requests': pending_activation_requests,
        'delegate_role_logs': delegate_role_logs,
    })


# ─────────────────────────────────────────────
# admin – user management  (staff/superuser only)
# ───────────────────────────────────────────��─

def _require_admin(request):
    return request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


@login_required(login_url="users:login_view")
def user_management_view(request):
    if not _require_admin(request):
        messages.error(request, "Access denied.", extra_tags="danger")
        return redirect("pages:home")

    users = User.objects.select_related("role").order_by("last_name", "first_name")
    roles = Role.objects.all()
    return render(request, "users/user_management.html", {"users": users, "roles": roles})


@login_required(login_url="users:login_view")
def toggle_user_active_view(request, user_id):
    if not _require_admin(request):
        messages.error(request, "Access denied.", extra_tags="danger")
        return redirect("pages:home")

    if request.method == "POST":
        target = get_object_or_404(User, pk=user_id)
        if target == request.user:
            messages.error(request, "You cannot deactivate your own account.", extra_tags="danger")
        else:
            target.is_active = not target.is_active
            target.save(update_fields=["is_active"])
            if target.is_active:
                if target.last_login:
                    send_verification_email(target)
            status = "activated" if target.is_active else "deactivated"
            messages.success(request, f"User {target.get_full_name()} has been {status}.")

    return redirect("users:user_management_view")


@login_required(login_url="users:login_view")
def change_user_role_view(request, user_id):
    if not _require_admin(request):
        messages.error(request, "Access denied.", extra_tags="danger")
        return redirect("pages:home")

    if request.method == "POST":
        target = get_object_or_404(User, pk=user_id)
        role_name = request.POST.get("role")
        try:
            role = Role.objects.get(name=role_name)
            target.role = role
            target.save(update_fields=["role"])
            if role.name == "subject":
                _create_patient(target)
            messages.success(request, f"Role updated to '{role.get_name_display()}' for {target.get_full_name()}.")
        except Role.DoesNotExist:
            messages.error(request, "Invalid role selected.", extra_tags="danger")

    return redirect("users:user_management_view")

@login_required(login_url="users:login_view")
def change_user_organization_view(request, user_id):
    if not _require_admin(request):
        messages.error(request, "Access denied.", extra_tags="danger")
        return redirect("pages:home")

    if request.method == "POST":
        target = get_object_or_404(User, pk=user_id)
        organization_name = (request.POST.get("organization_name") or "").strip()
        target.organization_name = organization_name
        target.save(update_fields=["organization_name"])
        messages.success(request, f"Organisation updated for {target.get_full_name()}.")

    return redirect("users:user_management_view")


# ─────────────────────────────────────────────
# admin – roles & permissions management
# ─────────────────────────────────────────────

@login_required(login_url="users:login_view")
def roles_permissions_view(request):
    if not _require_admin(request):
        messages.error(request, "Access denied.", extra_tags="danger")
        return redirect("pages:home")

    roles = Role.objects.prefetch_related("rolepermission_set__permission").all()
    all_permissions = CustomPermission.objects.order_by("name")

    # Build a matrix: {role_id: set of permission_ids}
    assigned = {}
    for role in roles:
        assigned[role.id] = set(
            role.rolepermission_set.values_list("permission_id", flat=True)
        )

    return render(request, "users/roles_permissions.html", {
        "roles": roles,
        "all_permissions": all_permissions,
        "assigned": assigned,
    })


@login_required(login_url="users:login_view")
def update_role_permissions_view(request):
    if not _require_admin(request):
        messages.error(request, "Access denied.", extra_tags="danger")
        return redirect("pages:home")

    if request.method == "POST":
        role_id = request.POST.get("role_id")
        role = get_object_or_404(Role, pk=role_id)
        selected_perm_ids = set(int(x) for x in request.POST.getlist("permissions"))

        # current assignments
        current_perm_ids = set(
            RolePermission.objects.filter(role=role).values_list("permission_id", flat=True)
        )

        to_add = selected_perm_ids - current_perm_ids
        to_remove = current_perm_ids - selected_perm_ids

        RolePermission.objects.filter(role=role, permission_id__in=to_remove).delete()
        for perm_id in to_add:
            RolePermission.objects.create(
                role=role,
                permission=CustomPermission.objects.get(pk=perm_id),
            )

        messages.success(request, f"Permissions updated for role '{role.get_name_display()}'.")

    return redirect("users:roles_permissions_view")
