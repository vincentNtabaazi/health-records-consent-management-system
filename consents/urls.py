from django.urls import path
from .views import (
    request_consent_view,
    request_organization_consent_view,
    review_pending_consents_view,
    approve_consent_view,
    reject_consent_view,
    withdraw_consent_view,
    consent_details,
    subject_sharing_preferences_view,
    my_subject_sharing_preferences_view,
    granted_records_view,
)

app_name = 'consents'

urlpatterns = [
    path('request/<int:patient_id>/', request_consent_view, name='request_consent'),
    path('request/organization/', request_organization_consent_view, name='request_organization_consent'),
    path('pending/', review_pending_consents_view, name='review_pending_consents'),
    path('my-preferences/', my_subject_sharing_preferences_view, name='my_subject_sharing_preferences'),
    path('subject-preferences/<int:patient_id>/', subject_sharing_preferences_view, name='subject_sharing_preferences'),
    path('<int:consent_id>/', consent_details, name='consent_details'),
    path('<int:consent_id>/approve/', approve_consent_view, name='approve_consent'),
    path('<int:consent_id>/reject/', reject_consent_view, name='reject_consent'),
    path('<int:consent_id>/withdraw/', withdraw_consent_view, name='withdraw_consent'),
    path('<int:consent_id>/records/', granted_records_view, name='granted_records'),
]
