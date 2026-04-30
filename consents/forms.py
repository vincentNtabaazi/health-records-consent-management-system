from collections import OrderedDict

from django import forms

from consents.models import Consent
from patients.models import Patient, PatientPermission
from users.models import RolePermission
from services.odrl import group_permissions_by_category, infer_data_category_from_permission, prettify_permission


ALLOWED_REQUESTER_ROLES = {'processor', 'researcher', 'regulator', 'insurance_agent'}


class ConsentRequestForm(forms.ModelForm):
    permission_ids = forms.MultipleChoiceField(
        label='Requested permissions',
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    class Meta:
        model = Consent
        fields = ['purpose', 'expiry_date', 'notes']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'purpose': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, requester=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.requester = requester
        self.allowed_permissions = []

        role_name = getattr(getattr(requester, 'role', None), 'name', None)
        if role_name in ALLOWED_REQUESTER_ROLES:
            self.allowed_permissions = [
                rp.permission
                for rp in RolePermission.objects.filter(role=requester.role).select_related('permission')
            ]

        self.fields['permission_ids'].choices = [
            (str(permission.id), permission.name)
            for permission in self.allowed_permissions
        ]
        self.grouped_permissions = group_permissions_by_category(self.allowed_permissions)

    def clean_permission_ids(self):
        selected = set(self.cleaned_data['permission_ids'])
        allowed = {str(permission.id) for permission in self.allowed_permissions}
        invalid = selected - allowed
        if invalid:
            raise forms.ValidationError('You selected permissions that are not allowed for your role.')
        return [int(item) for item in selected]


class OrganizationConsentRequestForm(ConsentRequestForm):
    """Request the same consent from every subject in one organisation."""

    organization_name = forms.ChoiceField(
        label='Subject organisation',
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta(ConsentRequestForm.Meta):
        fields = ['organization_name', 'purpose', 'expiry_date', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organizations = (
            Patient.objects
            .select_related('user')
            .exclude(user__organization_name__isnull=True)
            .exclude(user__organization_name__exact='')
            .values_list('user__organization_name', flat=True)
            .distinct()
            .order_by('user__organization_name')
        )
        self.fields['organization_name'].choices = [('', 'Select an organisation')] + [
            (organization, organization)
            for organization in organizations
        ]

    def clean_organization_name(self):
        organization_name = (self.cleaned_data.get('organization_name') or '').strip()
        if not organization_name:
            raise forms.ValidationError('Please choose a subject organisation.')
        has_subjects = Patient.objects.filter(user__organization_name=organization_name).exists()
        if not has_subjects:
            raise forms.ValidationError('No subjects were found in this organisation.')
        return organization_name


class SubjectSharingPreferencesForm(forms.Form):
    role_permission_ids = forms.MultipleChoiceField(
        label='Sharing preferences',
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, patient=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.patient = patient
        self.available_role_permissions = list(
            RolePermission.objects
            .exclude(role__name='subject')
            .select_related('role', 'permission')
            .order_by('role__name', 'permission__name')
        )

        self.fields['role_permission_ids'].choices = [
            (str(role_permission.id), f"{role_permission.role.get_name_display()} - {prettify_permission(role_permission.permission.name)}")
            for role_permission in self.available_role_permissions
        ]

        selected_ids = list(
            PatientPermission.objects
            .filter(patient=patient)
            .values_list('role_permission_id', flat=True)
        )
        if not self.is_bound:
            self.initial['role_permission_ids'] = [str(item) for item in selected_ids]

        grouped = OrderedDict()
        for role_permission in self.available_role_permissions:
            role_label = role_permission.role.get_name_display()
            grouped.setdefault(role_label, OrderedDict())
            category = infer_data_category_from_permission(role_permission.permission.name)
            grouped[role_label].setdefault(category, [])
            grouped[role_label][category].append({
                'id': role_permission.id,
                'permission_id': role_permission.permission_id,
                'permission_name': role_permission.permission.name,
                'label': prettify_permission(role_permission.permission.name),
                'category': category,
            })
        self.grouped_role_permissions = grouped

    def clean_role_permission_ids(self):
        selected = set(self.cleaned_data['role_permission_ids'])
        allowed = {str(role_permission.id) for role_permission in self.available_role_permissions}
        invalid = selected - allowed
        if invalid:
            raise forms.ValidationError('You selected invalid sharing preferences.')
        return [int(item) for item in selected]

    def save(self):
        selected_ids = set(self.cleaned_data['role_permission_ids'])
        existing_ids = set(
            PatientPermission.objects
            .filter(patient=self.patient)
            .values_list('role_permission_id', flat=True)
        )

        PatientPermission.objects.filter(patient=self.patient).exclude(role_permission_id__in=selected_ids).delete()

        PatientPermission.objects.bulk_create([
            PatientPermission(patient=self.patient, role_permission_id=role_permission_id)
            for role_permission_id in (selected_ids - existing_ids)
        ])
