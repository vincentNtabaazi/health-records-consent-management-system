from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password

from django.contrib.auth import get_user_model
from .models import Role, CustomPermission, RolePermission
from .forms import SignupForm, LoginForm, ProfileForm, ChangePasswordForm, DelegateForm
from .utils import authenticate

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
    """Let users with can_delegate=True assign or remove a delegate."""
    if not request.user.can_delegate:
        messages.error(request, "You do not have delegation rights.", extra_tags="danger")
        return redirect("users:profile_view")

    form = DelegateForm(
        request.POST or None,
        initial={"delegate_to": request.user.delegated_to},
    )

    if request.method == "POST":
        if form.is_valid():
            delegate = form.cleaned_data["delegate_to"]
            if delegate and delegate == request.user:
                form.add_error("delegate_to", "You cannot delegate to yourself.")
            else:
                request.user.delegated_to = delegate
                request.user.save(update_fields=["delegated_to"])
                if delegate:
                    messages.success(request, f"Authority delegated to {delegate.get_full_name()}.")
                else:
                    messages.success(request, "Delegation removed.")
                return redirect("users:profile_view")

    return render(request, "users/delegation.html", {"form": form})


# ─────────────────────────────────────────────
# admin – user management  (staff/superuser only)
# ─────────────────────────────────────────────

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
            messages.success(request, f"Role updated to '{role.get_name_display()}' for {target.get_full_name()}.")
        except Role.DoesNotExist:
            messages.error(request, "Invalid role selected.", extra_tags="danger")

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
