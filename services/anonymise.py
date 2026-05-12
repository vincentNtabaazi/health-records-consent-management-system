from collections import Counter

ROLE_PRIVACY_RULES = {

    "researcher": {
        "show_direct_identifiers": False,
        "show_exact_age": False,
        "show_full_postcode": False,
        "age_ranges": True,
        "k_anonymity": 5,
    },

    "processor": {
        "show_direct_identifiers": False,
        "show_exact_age": False,
        "show_full_postcode": False,
        "age_ranges": True,
        "k_anonymity": 3,
    },

    "regulator": {
        "show_direct_identifiers": True,
        "show_exact_age": True,
        "show_full_postcode": True,
        "age_ranges": False,
        "k_anonymity": 1,
    },

    "insurance_agent": {
        "show_direct_identifiers": True,
        "show_exact_age": True,
        "show_full_postcode": True,
        "age_ranges": False,
        "k_anonymity": 1,
    }
}

def get_age_range(age):

    if age < 18:
        return "0-17"

    elif age < 30:
        return "18-29"

    elif age < 40:
        return "30-39"

    elif age < 50:
        return "40-49"

    elif age < 60:
        return "50-59"

    else:
        return "60+"


def anonymize_postcodes(patients, k=5):

    postcode_prefixes = []

    for patient in patients:

        postcode = patient.user.postal_code or ""

        prefix = postcode.split(" ")[0]

        print('prefix', prefix)

        postcode_prefixes.append(prefix)

    counts = Counter(postcode_prefixes)

    anonymized = {}

    for patient in patients:

        postcode = patient.user.postal_code or ""

        prefix = postcode.split(" ")[0]

        if counts[prefix] >= k:
            anonymized[patient.id] = prefix

        else:
            anonymized[patient.id] = prefix[:2]

    print('anonymized', anonymized)

    return anonymized

def transform_patient_data(patient, log, privacy_rules, anonymized_postcodes):

    user = patient.user

    row = {}

    # Direct identifiers
    if privacy_rules["show_direct_identifiers"]:

        row["patient_first_name"] = user.first_name
        row["patient_last_name"] = user.last_name
        row["patient_email"] = user.email

    # Age handling
    if privacy_rules["show_exact_age"]:

        row["age"] = user.age

    elif privacy_rules["age_ranges"]:

        row["age_range"] = get_age_range(user.age)

    # Postcode handling
    if privacy_rules["show_full_postcode"]:

        row["postal_code"] = user.postal_code

    else:

        row["postal_code"] = anonymized_postcodes.get(patient.id)

    # Shared fields
    row["data_type"] = log.access_request.resource_type

    row["requestor"] = (
        log.access_request.requester.organization_name
    )

    row["consent_type"] = log.matched_consent.consent_type

    row["purpose"] = log.matched_consent.purpose

    return row