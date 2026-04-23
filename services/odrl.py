import json
from collections import defaultdict
from datetime import datetime

ODRL_CONTEXT = "http://www.w3.org/ns/odrl.jsonld"
HEALTH_PROFILE = "https://example.org/odrl/health-consent-profile/v1"
HEALTH_NS = "https://example.org/odrl/health#"


def infer_action_from_permission(permission_name: str) -> str:
    """can_read_diagnosis_records -> read"""
    parts = permission_name.split("_")
    return parts[1] if len(parts) >= 4 else "read"



def infer_data_category_from_permission(permission_name: str) -> str:
    """can_read_mental_health_records -> mental_health"""
    prefix = "can_"
    suffix = "_records"
    if permission_name.startswith(prefix) and permission_name.endswith(suffix):
        body = permission_name[len(prefix):-len(suffix)]
        action, _, category = body.partition("_")
        return category or "general"
    return "general"



def prettify_permission(permission_name: str) -> str:
    action = infer_action_from_permission(permission_name).replace("_", " ").title()
    category = infer_data_category_from_permission(permission_name).replace("_", " ").title()
    return f"{action} {category} records"



def group_permissions_by_category(permissions):
    grouped = defaultdict(list)
    for perm in permissions:
        grouped[infer_data_category_from_permission(perm.name)].append(
            {
                "id": perm.id,
                "name": perm.name,
                "label": prettify_permission(perm.name),
                "action": infer_action_from_permission(perm.name),
            }
        )
    return dict(grouped)



def _permission_rule(consent, permission, assignee_id=None):
    action = infer_action_from_permission(permission.name)
    category = infer_data_category_from_permission(permission.name)
    assignee_id = assignee_id or consent.data_processor_id

    return {
        "uid": f"urn:consent-rule:{consent.consent_id}:{permission.id}",
        "target": {
            "uid": f"urn:patient-asset:{consent.patient_id}:{category}",
            "type": f"{HEALTH_NS}MedicalRecordCategory",
            "category": category,
        },
        "assigner": {"uid": f"urn:user:{consent.patient_id}", "role": "assigner"},
        "assignee": {"uid": f"urn:user:{assignee_id}", "role": "assignee"},
        "action": f"{HEALTH_NS}{action}",
        "constraint": [
            {
                "leftOperand": f"{HEALTH_NS}purpose",
                "operator": "odrl:eq",
                "rightOperand": consent.purpose,
            },
            {
                "leftOperand": f"{HEALTH_NS}expiryDate",
                "operator": "odrl:lteq",
                "rightOperand": consent.expiry_date.isoformat() if consent.expiry_date else None,
            },
        ],
        "duty": [
            {"action": f"{HEALTH_NS}logAccess"},
            {"action": f"{HEALTH_NS}noRedisclosure"},
        ],
    }



def build_odrl_request_policy(consent, permissions):
    return {
        "@context": ODRL_CONTEXT,
        "uid": f"urn:consent-request:{consent.consent_id}",
        "type": "Request",
        "profile": HEALTH_PROFILE,
        "target": f"urn:patient:{consent.patient_id}",
        "permission": [_permission_rule(consent, permission) for permission in permissions],
        "status": "pending",
    }



def build_odrl_privacy_policy(consent, permissions):
    return {
        "@context": ODRL_CONTEXT,
        "uid": f"urn:consent-policy:{consent.consent_id}",
        "type": "Privacy",
        "profile": HEALTH_PROFILE,
        "target": f"urn:patient:{consent.patient_id}",
        "permission": [_permission_rule(consent, permission) for permission in permissions],
        "status": "active",
    }



def build_odrl_denial_policy(consent, permissions):
    prohibitions = []
    for permission in permissions:
        rule = _permission_rule(consent, permission)
        rule.pop("duty", None)
        prohibitions.append(rule)

    return {
        "@context": ODRL_CONTEXT,
        "uid": f"urn:consent-denial:{consent.consent_id}",
        "type": "Set",
        "profile": HEALTH_PROFILE,
        "target": f"urn:patient:{consent.patient_id}",
        "prohibition": prohibitions,
        "status": "denied",
    }



def mark_policy_revoked(policy_payload, revoked_at=None):
    payload = dict(policy_payload or {})
    payload["status"] = "withdrawn"
    payload["revokedAt"] = (revoked_at or datetime.utcnow()).isoformat()
    return payload



def action_uri(action: str) -> str:
    return f"{HEALTH_NS}{action}"



def evaluate_odrl_payload(policy_payload, *, action, category, purpose, assignee_id, when_date=None):
    """
    Very small evaluator for the ODRL profile used in this project.
    It checks assignee/action/category/purpose/expiry. Matching prohibition wins.
    """
    if not policy_payload:
        return False

    when_date = when_date.isoformat() if when_date else None
    requested_action_uri = action_uri(action)
    requested_assignee = f"urn:user:{assignee_id}"

    def _matches(rule):
        if rule.get("action") != requested_action_uri:
            return False

        assignee = (rule.get("assignee") or {}).get("uid")
        if assignee and assignee != requested_assignee:
            return False

        target = rule.get("target") or {}
        if isinstance(target, dict) and target.get("category") != category:
            return False

        for constraint in rule.get("constraint", []):
            left = constraint.get("leftOperand")
            right = constraint.get("rightOperand")
            operator = constraint.get("operator")

            if left.endswith("purpose") and right and purpose and right != purpose:
                return False

            if left.endswith("expiryDate") and right and when_date and operator == "odrl:lteq" and when_date > right:
                return False

        return True

    for rule in policy_payload.get("prohibition", []):
        if _matches(rule):
            return False

    for rule in policy_payload.get("permission", []):
        if _matches(rule):
            return True

    return False



def pretty_json(value):
    return json.dumps(value or {}, ensure_ascii=False, indent=2)
