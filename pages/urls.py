from django.urls import path
from .views import *
from .views_access_history import access_history_view

app_name = 'pages'

urlpatterns = [
    path('', dashboard_view, name='home'),
    path('consent_records/', consent_records, name='consent_records'),
    path('policies/', policies, name='policies'),
    path('data_subjects/', data_subjects, name='data_subjects'),
    path('dashboard/', dashboard_view, name='dashboard_view'),
    path('medical_records/', medical_records, name='medical_records'),
    path('access_request/', access_request_view, name='access_request'),
    path('access_history/', access_history_view, name='access_history'),
    path('compliance/', compliance_dashboard_view, name='compliance_dashboard'),
    path('my_data/', my_data_view, name='my_data'),
]

