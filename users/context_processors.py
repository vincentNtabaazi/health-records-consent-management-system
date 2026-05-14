from .utils import get_available_delegations, get_current_acting_context


def acting_context(request):
    """Add acting context to all templates."""
    if not request.user.is_authenticated:
        return {}

    current_delegation = get_current_acting_context(request)

    return {
        'available_delegations': get_available_delegations(request.user),
        'current_acting_delegation': current_delegation,
        'is_acting_as_proxy': current_delegation is not None,
    }