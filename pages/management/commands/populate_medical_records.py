# your_app/management/commands/populate_medical_records.py

import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from patients.models import MedicalRecord, Patient


class Command(BaseCommand):
    help = "Populate the MedicalRecord table with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            '--num_records',
            type=int,
            default=100,
            help='Number of medical records to create'
        )

        parser.add_argument(
            '--patient_start',
            type=int,
            default=1,
            help='Starting patient ID'
        )

        parser.add_argument(
            '--patient_end',
            type=int,
            default=5,
            help='Ending patient ID'
        )

    def handle(self, *args, **kwargs):

        num_records = kwargs['num_records']
        patient_id_start = kwargs['patient_start']
        patient_id_end = kwargs['patient_end']

        data_category_choices = [
            choice[0]
            for choice in MedicalRecord.DATA_CATEGORY_CHOICES
        ]

        # Ensure patients exist
        patient_ids = list(range(patient_id_start, patient_id_end + 1))

        existing_patients = Patient.objects.filter(
            id__in=patient_ids
        )

        if not existing_patients.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"No patients found in range "
                    f"{patient_id_start}-{patient_id_end}"
                )
            )
            return

        titles_by_category = {
            'diagnosis': [
                "Influenza Diagnosis",
                "Hypertension Screening",
                "Diabetes Management Plan",
                "Asthma Attack Follow-up",
                "Migraine Assessment"
            ],

            'treatment': [
                "Antibiotic Prescription",
                "Physical Therapy Session",
                "Minor Surgical Procedure",
                "Chemotherapy Cycle 1",
                "Immunotherapy Start"
            ],

            'mental_health': [
                "Anxiety Disorder Consultation",
                "Depression Therapy Session",
                "PTSD Initial Assessment",
                "Bipolar Disorder Medication Review",
                "Counselling Session Note"
            ],

            'billing': [
                "Insurance Claim Submission",
                "Co-pay Received",
                "Outstanding Balance Reminder",
                "Procedure Code Review",
                "Payment Plan Setup"
            ],

            'lab_results': [
                "Complete Blood Count Results",
                "Urinalysis Report",
                "Cholesterol Panel",
                "Thyroid Function Test",
                "Pathology Report"
            ],

            'medication': [
                "New Prescription: Amoxicillin",
                "Medication Refill Request",
                "Dosage Adjustment: Insulin",
                "Medication Review for Side Effects",
                "Vaccine Administration Record"
            ],

            'allergies': [
                "New Allergy Identified: Penicillin",
                "Allergy Test Results",
                "Allergy Medication Prescribed",
                "Update: No Known Allergies",
                "Food Allergy Consultation"
            ],

            'immunization': [
                "Flu Shot Administered",
                "MMR Vaccine Update",
                "Tetanus Booster Given",
                "COVID-19 Vaccine Dose 1",
                "Hepatitis B Vaccination Series"
            ],
        }

        records_created = 0

        for _ in range(num_records):

            try:
                random_patient = random.choice(existing_patients)

                random_category = random.choice(
                    data_category_choices
                )

                random_title = random.choice(
                    titles_by_category.get(
                        random_category,
                        ["General Medical Record"]
                    )
                )

                # Random datetime within last year
                days_ago = random.randint(1, 365)

                random_date = timezone.now() - timedelta(
                    days=days_ago,
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )

                MedicalRecord.objects.create(
                    patient=random_patient,
                    title=random_title,
                    data_category=random_category,
                    created_at=random_date,
                )

                records_created += 1

            except Exception as e:

                self.stdout.write(
                    self.style.WARNING(
                        f"Error creating record: {e}"
                    )
                )

                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created "
                f"{records_created} medical records."
            )
        )