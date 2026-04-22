# Health Records Consent Management System

A prototype system for managing patient data consent and enforcing governance policies, built for the Data Economy module group project.

**Topic: Data Governance, Consent, Policies and Compliance**

---

## Prerequisites

- Python 3.10+
- MySQL 8.0+

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/vincentNtabaazi/health-records-consent-management-system.git
cd health-records-consent-management-system
```

**2. Create and activate virtual environment**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install django mysqlclient
```

**4. Create MySQL database**

```sql
CREATE DATABASE cms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

**5. Update database password**

Open `CMS/settings.py` and update the `PASSWORD` field to match your MySQL root password.

**6. Run migrations**

```bash
python manage.py makemigrations
python manage.py migrate
```

**7. Create superuser**

```bash
python manage.py createsuperuser
```

**8. Start the server**

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

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