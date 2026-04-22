# Health Records Consent Management System

A prototype data governance system built for the **Data Economy** module coursework. The system demonstrates how consent-based access control, policy evaluation, audit logging, and compliance checking can be implemented in a real healthcare data context.

---

## Project Overview

This system addresses the problem of **governing access to sensitive health records** in compliance with data protection principles (e.g., GDPR). It implements:

- **Consent Management** — patients grant or revoke access to their health data
- **Policy Evaluation Engine** — every access request is evaluated against active consent and role-based rules
- **Audit Logging** — every decision is recorded with full context
- **Compliance Checker** — automated scanning of audit logs for governance violations

---

## System Architecture
┌─────────────────────────────────────────────┐
│              Frontend (Django Templates)     │
│  Dashboard | Consent Records | Access Request│
│  Compliance Dashboard | Medical Records      │
└──────────────────┬──────────────────────────┘
│
┌──────────────────▼──────────────────────────┐
│              Django Views (pages/)           │
└──┬───────────────┬──────────────────────────┘
│               │
┌──▼──────┐  ┌─────▼──────────────────────────┐
│ Consent │  │ services/                       │
│ Manager │  │   policy_engine.py  (rules)     │
│         │  │   audit_logger.py   (recording) │
│         │  │   compliance_checker.py (scan)  │
└──┬──────┘  └─────┬──────────────────────────┘
│               │
┌──▼───────────────▼──────────────────────────┐
│                MySQL Database                │
│  users | patients | consents | AccessRequest │
│  DecisionLog | MedicalRecord | ConsentPolicy │
└─────────────────────────────────────────────┘

---

## Tech Stack

- **Backend**: Django 6.0, Python 3.13
- **Database**: MySQL
- **Frontend**: Bootstrap 5.3, Chart.js
- **Policy Language**: ODRL (Open Digital Rights Language)

---

## Installation

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- Git

### Step 1: Clone the repository

```bash
git clone <repository-url>
cd health-records-consent-management-system
```

### Step 2: Create and activate virtual environment

```bash
# Create
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate
```

### Step 3: Install dependencies

```bash
pip install django mysqlclient
```

### Step 4: Configure database

Create a MySQL database called `cms`:

```sql
CREATE DATABASE cms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The default database settings in `CMS/settings.py` are:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'cms',
        'USER': 'root',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

Update `PASSWORD` to match your MySQL root password.

### Step 5: Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Create a superuser

```bash
python manage.py createsuperuser
```

### Step 7: Start the server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

---

## Key Pages

| URL | Description |
|---|---|
| `/` | Dashboard — consent overview and recent activity |
| `/consent_records/` | View and manage all consent records |
| `/access_request/` | Submit and evaluate a data access request |
| `/compliance/` | Compliance dashboard and audit log |
| `/data_subjects/` | List of registered patients |
| `/medical_records/` | Browse medical records by category |
| `/admin/` | Django admin panel |

---

## Testing the Governance Logic

### Step 1: Set up test roles and users

```bash
python manage.py shell
```

```python
from users.models import Role, RolePermission, CustomPermission
from django.contrib.auth import get_user_model
from patients.models import Patient
import datetime

User = get_user_model()

# Create roles
role_subject,    _ = Role.objects.get_or_create(name='subject')
role_processor,  _ = Role.objects.get_or_create(name='processor')
role_researcher, _ = Role.objects.get_or_create(name='researcher')

# Create permission
perm, _ = CustomPermission.objects.get_or_create(name='can_read_lab_results_records')
RolePermission.objects.get_or_create(role=role_processor,  permission=perm)
RolePermission.objects.get_or_create(role=role_researcher, permission=perm)

# Create users
patient_user = User.objects.create_user(
    username='patient_alice', password='test1234',
    first_name='Alice', last_name='Smith', role=role_subject,
)
doctor = User.objects.create_user(
    username='doctor_bob', password='test1234',
    first_name='Bob', last_name='Jones', role=role_processor,
)
researcher = User.objects.create_user(
    username='researcher_carol', password='test1234',
    first_name='Carol', last_name='White', role=role_researcher,
)

# Create patient profile
patient = Patient.objects.create(
    user=patient_user, nhs_number='NHS123456',
    date_of_birth='1990-05-15',
)
```

### Step 2: Run demo scenarios

```python
from consents.models import Consent
from services.policy_engine import evaluate_access
from services.compliance_checker import check_violations

# Grant consent
consent = Consent.objects.create(
    patient=patient_user,
    data_processor=doctor,
    purpose='treatment',
    data_type='lab_results',
    status='active',
    expiry_date=datetime.date(2026, 12, 31),
)

# Scenario 1: doctor requests lab_results for treatment -> ALLOW
log1 = evaluate_access(doctor, patient, 'lab_results', 'treatment')
print(log1.decision, log1.reason)

# Scenario 2: researcher requests lab_results -> ALLOW WITH REDACTION
log2 = evaluate_access(researcher, patient, 'lab_results', 'research')
print(log2.decision, log2.reason)

# Scenario 3: empty purpose -> DENY
log3 = evaluate_access(doctor, patient, 'lab_results', '')
print(log3.decision, log3.reason)

# Scenario 4: withdraw consent
consent.withdraw_consent()

# Scenario 5: doctor requests after withdrawal -> DENY
log4 = evaluate_access(doctor, patient, 'lab_results', 'treatment')
print(log4.decision, log4.reason)

# Scenario 6: compliance report
report = check_violations(patient)
print(f"Compliance rate: {report['compliance_rate']}%")
print(f"Violations: {report['violation_count']}")
```

### Expected outcomes

| Scenario | Role | Purpose | Expected Decision |
|---|---|---|---|
| Active consent exists | doctor | treatment | ALLOW |
| Researcher role | researcher | research | ALLOW WITH REDACTION |
| Empty purpose | doctor | (empty) | DENY |
| After consent withdrawal | doctor | treatment | DENY |
| No consent record | anyone | any | DENY |

---

## Governance Features

### Policy Evaluation Rules (in priority order)

1. Purpose field must not be empty → otherwise DENY
2. An active consent record must exist → otherwise DENY
3. Consent must not be withdrawn → otherwise DENY
4. Consent must not be expired → otherwise DENY
5. Requester must have a role assigned → otherwise DENY
6. Role must have the required permission → otherwise DENY
7. Researcher role → ALLOW WITH REDACTION (anonymised data only)
8. Doctor role + treatment purpose → ALLOW (full access)
9. All other valid cases → ALLOW

### Compliance Violation Types

| Type | Severity | Description |
|---|---|---|
| `POST_WITHDRAWAL_ACCESS` | HIGH | Access allowed after consent was withdrawn |
| `RESEARCHER_FULL_ACCESS` | HIGH | Researcher received full instead of redacted access |
| `EMPTY_PURPOSE_ALLOWED` | MEDIUM | Request with no purpose was not denied |
| `ALLOW_WITHOUT_CONSENT` | HIGH | Access allowed with no matched consent record |

---

## Project Structure
health-records-consent-management-system/
├── CMS/                    # Django project settings
├── consents/               # Consent models and views
│   ├── models.py           # Consent, AccessRequest, DecisionLog
│   └── admin.py            # Admin registration
├── patients/               # Patient and medical record models
│   └── models.py           # Patient, MedicalRecord, ConsentPolicy
├── users/                  # User and role models
│   └── models.py           # User, Role, RolePermission
├── pages/                  # Frontend views and URLs
│   ├── views.py            # All page views including governance pages
│   └── urls.py             # URL routing
├── services/               # Core governance logic
│   ├── policy_engine.py    # Access evaluation and governance rules
│   ├── audit_logger.py     # Audit trail recording
│   ├── compliance_checker.py # Violation detection
│   └── odrl.py             # ODRL policy builder
├── templates/              # HTML templates
│   ├── base.html
│   └── pages/
│       ├── access_request.html
│       ├── compliance_dashboard.html
│       └── ...
└── README.md

---

## Team

Built as part of the **Data Economy** module group project.

Topic: **Data Governance, Consent, Policies and Compliance**