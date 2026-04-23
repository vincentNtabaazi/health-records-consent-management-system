from django.urls import path
from .views import *

app_name = 'patients'

urlpatterns = [
    path('<int:patient_id>/timeline/', patient_medical_timeline, name='patient_medical_timeline'),
    #path('<int:patient_id>/timeline/update', update_patient_permissions, name='update_patient_permissions'),
]