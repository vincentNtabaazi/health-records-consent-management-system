# Health Records Consent Management System

A prototype system for managing patient data consent and enforcing governance policies, built for the Data Economy module group project.

**Topic: Data Governance, Consent, Policies and Compliance**

---

## Prerequisites

- Python 3.10+
- MySQL 8.0+

---

## Installation

**Clone the repository**

```bash
git clone https://github.com/vincentNtabaazi/health-records-consent-management-system.git
cd health-records-consent-management-system
```

**Create and activate virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

## 1. Delete all migration files except __init__.py.

MacOS/Linux
```bash
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete
```

Windows Powershell
```bash
Get-ChildItem -Recurse -Path .\* -Include *.py |
Where-Object {
    $_.FullName -match "\\migrations\\" -and
    $_.Name -ne "__init__.py"
} | Remove-Item
```

## 2. Delete Python cache files (recommended)

MacOS/Linux
```bash
find . -name "__pycache__" -type d -exec rm -r {} +
```

Windows Powershell
```bash
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
```

## 3. Reinstall Django:
```bash
pip uninstall django -y
pip install django
```

```bash
pip install pymysql
```

## 4. Recreate migrations
```bash
python manage.py makemigrations
```

## 5. Apply migrations
```bash
python manage.py migrate
```

## 6. Create admin user
```bash
python manage.py createsuperuser
```

## 7. Create the roles on the system
```bash
python manage.py create_roles  
```  

## 8. Assign the roles different permissions on the system
```bash
python manage.py assign_role_permissions
```  

## 9. Create demo users. After running this command user accounts and passwords stored in project home directory in a file called demo_user_credentials.txt
```bash
python manage.py create_demo_users
```

## 10. Create the permissions that different data subjects can give on their documents
```bash
python manage.py generate_medical_permissions
```


## 11. Create the medical records for data subjects. By default 100 records will be created for users with 1 to 5 as long as the user is a data subject.
```bash
python manage.py populate_medical_records
```

You can use this for a custom number of records and user ids, just change the numbers. but make sure the patient_end id exists so you must create 10 users before running this command
```bash
python manage.py populate_medical_records --num_records 200 --patient_start 1 --patient_end 10
```

## 12. Run the server.
```bash
python manage.py runserver
```

Then you can login to the system and continue using the demo accounts

## Key Pages

| URL | Description |
|---|---|
| `/` | Dashboard |
| `/access_request/` | Submit and evaluate a data access request |
| `/compliance/` | Compliance dashboard and audit log |
| `/consent_records/` | View and manage consent records |
| `/admin/` | Django admin panel |

---

## Governance Features

Every access request is evaluated against these rules in order:

1. Purpose must not be empty → DENY
2. Active consent must exist → DENY
3. Consent must not be withdrawn → DENY
4. Consent must not be expired → DENY
5. Requester must have a role → DENY
6. Role must have permission → DENY
7. Researcher role → ALLOW WITH REDACTION
8. Doctor + treatment → ALLOW
9. All other valid cases → ALLOW