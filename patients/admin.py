from django.contrib import admin
from patients.models import Patient, MedicalRecord, PatientPermission

# Register your models here.
admin.site.register(Patient)
admin.site.register(MedicalRecord)
admin.site.register(PatientPermission)