from django.urls import path
from .views import (
    login_view,
    signup_view,
    logout_view,
    profile_view,
    change_password_view,
    delegation_view,
    user_management_view,
    toggle_user_active_view,
    change_user_role_view,
    change_user_organization_view,
    roles_permissions_view,
    update_role_permissions_view,
)

app_name = "users"

urlpatterns = [
    # ── auth ──────────────────────────────────
    path("login/", login_view, name="login_view"),
    path("signup/", signup_view, name="signup_view"),
    path("logout/", logout_view, name="logout_view"),

    # ── profile ───────────────────────────────
    path("profile/", profile_view, name="profile_view"),
    path("profile/password/", change_password_view, name="change_password_view"),
    path("profile/delegate/", delegation_view, name="delegation_view"),

    # ── admin: user management ────────────────
    path("admin/users/", user_management_view, name="user_management_view"),
    path(
        "admin/users/<int:user_id>/toggle/",
        toggle_user_active_view,
        name="toggle_user_active_view",
    ),
    path(
        "admin/users/<int:user_id>/change-role/",
        change_user_role_view,
        name="change_user_role_view",
    ),
    path(
        "admin/users/<int:user_id>/change-organization/",
        change_user_organization_view,
        name="change_user_organization_view",
    ),

    # ── admin: roles & permissions ────────────
    path("admin/roles/", roles_permissions_view, name="roles_permissions_view"),
    path(
        "admin/roles/update/",
        update_role_permissions_view,
        name="update_role_permissions_view",
    ),
]