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
