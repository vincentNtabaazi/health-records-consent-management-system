from django.urls import path
from .views import *

app_name = 'consent'

urlpatterns = [
    path('<int:pk>/', consent_details, name='consent_details'),
]