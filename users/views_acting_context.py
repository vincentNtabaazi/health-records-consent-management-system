# Acting Context Switcher views
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect

from .models import Delegation


@login_required
def set_acting_context_view(request, data_subject_id):
    """Set acting context via GET URL."""
    # Verify delegation exists and is active
    delegation = Delegation.objects.filter(
        data_subject_id=data_subject_id,
        proxy=request.user,
        status='active'
    ).first()

    if not delegation:
        messages.error(request, 'Invalid delegation.')
        return redirect('pages:home')

    request.session['acting_for_user_id'] = delegation.data_subject_id
    messages.success(request, f'Now acting as {delegation.data_subject.get_full_name()}.')

    referer = request.META.get('HTTP_REFERER')
    return redirect(referer or 'pages:home')


@login_required
def clear_acting_context_view(request):
    """Clear acting context via GET URL."""
    request.session.pop('acting_for_user_id', None)
    messages.success(request, 'Now acting as myself.')

    referer = request.META.get('HTTP_REFERER')
    return redirect(referer or 'pages:home')