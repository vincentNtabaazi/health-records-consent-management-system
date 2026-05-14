import re
from django.contrib.auth import get_user_model

def check_if_email(username):
    email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    if re.match(email_regex, username):
        return username
    else:
        return None

def authenticate(password, username):
    email = check_if_email(username)
    User = get_user_model()

    try:
        if email:
            user = User.objects.get(email=email)
            if user.check_password(password):
                return user
            return None
        elif username:
            user = User.objects.get(username=username)
            if user.check_password(password):
                return user
            return None
    except User.DoesNotExist:
        return None

def get_role(request):
    if request.user:
        return request.user.role.get_name_display()
    else:
        return None


# Acting Context Switcher helpers
def get_available_delegations(user):
    """Get all active delegations where user is the proxy."""
    from .models import Delegation
    return Delegation.objects.filter(
        proxy=user,
        status='active'
    ).select_related('data_subject')


def get_current_acting_context(request):
    """Get current acting context, re-validates each time."""
    from .models import Delegation

    acting_for_user_id = request.session.get('acting_for_user_id')
    if not acting_for_user_id:
        return None

    # Verify still active
    delegation = Delegation.objects.filter(
        data_subject_id=acting_for_user_id,
        proxy=request.user,
        status='active'
    ).select_related('data_subject').first()

    if not delegation:
        request.session.pop('acting_for_user_id', None)
        return None

    return delegation


def set_acting_context(request, data_subject_id):
    """Set acting context."""
    from .models import Delegation

    delegation = Delegation.objects.filter(
        data_subject_id=data_subject_id,
        proxy=request.user,
        status='active'
    ).first()

    if delegation:
        request.session['acting_for_user_id'] = data_subject_id
        return True
    return False


def clear_acting_context(request):
    """Clear acting context."""
    request.session.pop('acting_for_user_id', None)


def get_effective_user(request):
    """Get effective user: if acting as proxy, return data_subject; otherwise return request.user."""
    context = get_current_acting_context(request)
    if context:
        return context.data_subject
    return request.user