from django.contrib import admin

from consents.models import Consent


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = (
        'consent_id',
        'patient',
        'data_processor',
        'data_type',
        'status',
        'consent_type',
        'expiry_date',
        'created_date',
    )
    list_filter = ('status', 'consent_type', 'policy_evaluation_result')
    search_fields = ('consent_id', 'patient__username', 'data_processor__username', 'purpose')
    readonly_fields = ('consent_id', 'created_date', 'decision_date')




from consents.models import AccessRequest, DecisionLog


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'requester',
        'patient',
        'resource_type',
        'purpose',
        'action',
        'status',
        'requested_at',
    )
    list_filter = ('status', 'action', 'purpose')
    search_fields = ('requester__username', 'resource_type')
    readonly_fields = ('requested_at',)


@admin.register(DecisionLog)
class DecisionLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'access_request',
        'decision',
        'compliance_status',
        'matched_consent',
        'checked_at',
    )
    list_filter = ('decision', 'compliance_status')
    search_fields = ('reason', 'access_request__requester__username')
    readonly_fields = ('checked_at',)