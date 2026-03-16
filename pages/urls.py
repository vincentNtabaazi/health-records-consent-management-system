from django.urls import path
from .views import *

app_name = 'pages'

urlpatterns = [
    path('', dashboard_view, name='home'),
    path('consent_records/', consent_records, name='consent_records'),
    path('policies/', policies, name='policies'),
    path('data_subjects/', data_subjects, name='data_subjects'),
    path('dashboard/', dashboard_view, name='dashboard_view'),
]

