import csv
import random
from datetime import datetime, timedelta

# --- Configuration ---
NUM_CONSENTS = 20
PATIENT_USER_IDS = [3, 7, 8, 9, 10, 12]
PROCESSOR_USER_IDS = [5, 11, 13, 14, 15]

DATA_TYPES = [
    "Medical History",
    "Lab Results",
    "Genomic Data",
    "Prescription History",
    "Appointment Data",
    "Billing Information",
    "Insurance Details",
    "Vital Signs",
    "Imaging Scans (X-Ray, MRI)",
]

PURPOSES = [
    "Treatment and Care",
    "Medical Research",
    "Billing and Insurance Claims",
    "Hospital Operations",
    "Public Health Reporting",
    "Patient Communication",
    "Quality Improvement",
    "Drug Development",
]

CONSENT_TYPE_CHOICES = ['explicit', 'opt-in']  # Simplified for dummy data
STATUS_CHOICES = ['active', 'withdrawn', 'expired', 'pending']
POLICY_EVALUATION_CHOICES = ['compliant', 'non-compliant', 'n/a']


def generate_dummy_consent_data(num_records):
    records = []
    for i in range(1, num_records + 1):
        consent_id = f"CONSENT-{i:03d}-{random.randint(1000, 9999)}"
        patient_id = random.choice(PATIENT_USER_IDS)
        data_processor_id = random.choice(PROCESSOR_USER_IDS)
        data_type = random.choice(DATA_TYPES)
        purpose = random.choice(PURPOSES)
        consent_type = random.choice(CONSENT_TYPE_CHOICES)
        policy_evaluation_result = random.choice(POLICY_EVALUATION_CHOICES)
        status = random.choice(STATUS_CHOICES)

        created_date = datetime.now() - timedelta(days=random.randint(1, 365))

        decision_date = None
        expiry_date = None

        if status == 'active':
            decision_date = created_date + timedelta(minutes=random.randint(5, 60))
            expiry_date = created_date + timedelta(days=random.randint(30, 730))  # 1 month to 2 years
        elif status == 'withdrawn':
            decision_date = created_date + timedelta(days=random.randint(5, 180))
            expiry_date = None  # Withdrawn consents usually don't have an expiry
        elif status == 'expired':
            decision_date = created_date + timedelta(minutes=random.randint(5, 60))
            expiry_date = created_date + timedelta(days=random.randint(10, 30))  # Expired recently
            if expiry_date > datetime.now():  # Make sure it's actually expired
                expiry_date = datetime.now() - timedelta(days=random.randint(1, 5))

        # Format dates for CSV
        created_date_str = created_date.strftime('%Y-%m-%d %H:%M:%S')
        decision_date_str = decision_date.strftime('%Y-%m-%d %H:%M:%S') if decision_date else ''
        expiry_date_str = expiry_date.strftime('%Y-%m-%d %H:%M:%S') if expiry_date else ''

        records.append({
            "consent_id": consent_id,
            "patient_id": patient_id,
            "data_processor_id": data_processor_id,
            "data_type": data_type,
            "purpose": purpose,
            "consent_type": consent_type,
            "policy_evaluation_result": policy_evaluation_result,
            "status": status,
            "created_date": created_date_str,
            "decision_date": decision_date_str,
            "expiry_date": expiry_date_str,
            "notes": f"Generated note for {data_type} consent."
        })
    return records


# --- Generate and Write to CSV ---
dummy_data = generate_dummy_consent_data(NUM_CONSENTS)

csv_file_path = 'dummy_consents.csv'
fieldnames = list(dummy_data[0].keys())

with open(csv_file_path, 'w', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(dummy_data)

print(f"'{NUM_CONSENTS}' dummy consent records successfully generated and saved to '{csv_file_path}'")