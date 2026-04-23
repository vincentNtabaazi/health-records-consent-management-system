from django import forms
from django.contrib.auth import get_user_model
from .models import Role

User = get_user_model()


class SignupForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(label="Email address")
    organisation = forms.CharField(max_length=255, required=False, label="Organisation")
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        to_field_name="name",
        empty_label="Select your role",
        label="Role",
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput, min_length=8, label="Password"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput, label="Confirm password"
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned


class LoginForm(forms.Form):
    username = forms.CharField(label="Email or Username")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "organization_name"]
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "organization_name": "Organisation",
        }


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(widget=forms.PasswordInput, label="Current password")
    new_password = forms.CharField(
        widget=forms.PasswordInput, min_length=8, label="New password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput, label="Confirm new password"
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", "New passwords do not match.")
        return cleaned


class DelegateForm(forms.Form):
    """Allow a user with can_delegate=True to assign a delegate."""
    delegate_to = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        empty_label="— Remove delegation —",
        label="Delegate authority to",
    )
