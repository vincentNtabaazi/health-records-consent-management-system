from django.urls import path
from .views import *

app_name = 'pages'

urlpatterns = [
    path('', dashboard_view, name='home'),
    path('policies/', policies, name='policies'),
    path('data_subjects/', data_subjects, name='data_subjects'),
    path('dashboard/', dashboard_view, name='dashboard_view'),
    path('medical_records/', medical_records, name='medical_records'),
    path('access_request/', access_request_view, name='access_request'),
    path('compliance/', compliance_dashboard_view, name='compliance_dashboard'),
]

