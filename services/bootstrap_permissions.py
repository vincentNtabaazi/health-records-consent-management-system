from users.models import Role, CustomPermission, RolePermission


DEFAULT_ROLE_MATRIX = {
    "subject": {
        "diagnosis": ["read"],
        "treatment": ["read"],
        "mental_health": ["read"],
        "billing": ["read"],
        "lab_results": ["read"],
        "medication": ["read"],
        "allergies": ["read"],
        "immunization": ["read"],
    },
    "processor": {
        "diagnosis": ["read"],
        "treatment": ["read", "update"],
        "billing": ["read"],
        "lab_results": ["read"],
        "medication": ["read"],
        "allergies": ["read"],
        "immunization": ["read"],
    },
    "researcher": {
        "diagnosis": ["read"],
        "lab_results": ["read"],
        "immunization": ["read"],
    },
    "insurance_agent": {
        "billing": ["read"],
        "treatment": ["read"],
    },
    "regulator": {
        "diagnosis": ["read"],
        "treatment": ["read"],
        "billing": ["read"],
        "lab_results": ["read"],
        "medication": ["read"],
        "allergies": ["read"],
        "immunization": ["read"],
    },
}



def bootstrap_default_role_permissions():
    for role_name, matrix in DEFAULT_ROLE_MATRIX.items():
        role, _ = Role.objects.get_or_create(name=role_name)
        for category, actions in matrix.items():
            for action in actions:
                perm_name = f"can_{action}_{category}_records"
                permission, _ = CustomPermission.objects.get_or_create(name=perm_name)
                RolePermission.objects.get_or_create(role=role, permission=permission)
