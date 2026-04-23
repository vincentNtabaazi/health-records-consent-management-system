import random
from datetime import datetime, timedelta
from django.utils import timezone
from patients.models import MedicalRecord, Patient
from users.models import CustomPermission


def populate_medical_records(num_records=100, patient_id_start=7, patient_id_end=16):
    """
    Populates the MedicalRecord table with sample data.

    Args:
        num_records (int): The number of medical records to create.
        patient_id_start (int): The starting ID for patient foreign keys.
        patient_id_end (int): The ending ID for patient foreign keys (inclusive).
    """
    data_category_choices = [choice[0] for choice in MedicalRecord.DATA_CATEGORY_CHOICES]

    # Ensure patients exist for the given range
    patient_ids = list(range(patient_id_start, patient_id_end + 1))
    existing_patients = Patient.objects.filter(id__in=patient_ids)

    if not existing_patients.exists():
        print(f"No patients found in the range {patient_id_start}-{patient_id_end}. Please create some patients first.")
        return

    titles_by_category = {
        'diagnosis': [
            "Influenza Diagnosis", "Hypertension Screening", "Diabetes Management Plan",
            "Asthma Attack Follow-up", "Migraine Assessment"
        ],
        'treatment': [
            "Antibiotic Prescription", "Physical Therapy Session", "Minor Surgical Procedure",
            "Chemotherapy Cycle 1", "Immunotherapy Start"
        ],
        'mental_health': [
            "Anxiety Disorder Consultation", "Depression Therapy Session", "PTSD Initial Assessment",
            "Bipolar Disorder Medication Review", "Counselling Session Note"
        ],
        'billing': [
            "Insurance Claim Submission", "Co-pay Received", "Outstanding Balance Reminder",
            "Procedure Code Review", "Payment Plan Setup"
        ],
        'lab_results': [
            "Complete Blood Count Results", "Urinalysis Report", "Cholesterol Panel",
            "Thyroid Function Test", "Pathology Report"
        ],
        'medication': [
            "New Prescription: Amoxicillin", "Medication Refill Request", "Dosage Adjustment: Insulin",
            "Medication Review for Side Effects", "Vaccine Administration Record"
        ],
        'allergies': [
            "New Allergy Identified: Penicillin", "Allergy Test Results", "Allergy Medication Prescribed",
            "Update: No Known Allergies", "Food Allergy Consultation"
        ],
        'immunization': [
            "Flu Shot Administered", "MMR Vaccine Update", "Tetanus Booster Given",
            "COVID-19 Vaccine Dose 1", "Hepatitis B Vaccination Series"
        ],
    }

    records_created = 0
    for _ in range(num_records):
        try:
            random_patient = random.choice(existing_patients)
            random_category = random.choice(data_category_choices)
            random_title = random.choice(titles_by_category.get(random_category, ["General Medical Record"]))

            # Generate a random datetime within the last year
            days_ago = random.randint(1, 365)
            random_date = timezone.now() - timedelta(days=days_ago, hours=random.randint(0, 23),
                                                     minutes=random.randint(0, 59))

            MedicalRecord.objects.create(
                patient=random_patient,
                title=random_title,
                data_category=random_category,
                created_at=random_date,
            )
            records_created += 1
        except Exception as e:
            print(f"Error creating record: {e}")
            continue

    print(f"Successfully created {records_created} medical records.")

def generate_medical_permissions():

    actions = ["create", "read", "edit", "delete"]

    permissions = []

    for value, display in MedicalRecord.DATA_CATEGORY_CHOICES:
        for action in actions:
            perm_name = f"can_{action}_{value}_records"

            # Avoid duplicates
            obj, created = CustomPermission.objects.get_or_create(name=perm_name)

            if created:
                permissions.append(perm_name)

    return permissions