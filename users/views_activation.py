# Processor delegation activation view
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import transaction
from django.utils import timezone

from .models import Delegation, DelegationLog, DelegationActivation


@login_required(login_url="users:login_view")
def activation_requests_view(request):
    """Processor Delegation Activation - Request and confirm delegation activations."""
    # Check: only processor role can access
    user_role = getattr(getattr(request.user, 'role', None), 'name', None)
    if user_role != 'processor':
        messages.error(request, 'Only processors can access this page.', extra_tags='danger')
        return redirect('pages:home')

    # First section: accepted delegations that can request activation
    accepted_delegations = Delegation.objects.filter(
        status='accepted'
    ).select_related('data_subject', 'proxy')

    # Get pending activations to mark which delegations already have pending requests
    pending_activations = DelegationActivation.objects.filter(
        status='pending'
    ).values_list('delegation_id', flat=True)

    # Second section: pending activation requests (that user did NOT initiate)
    pending_requests = DelegationActivation.objects.filter(
        status='pending'
    ).exclude(
        initiated_by=request.user
    ).select_related('delegation__data_subject', 'delegation__proxy', 'initiated_by')

    # Third section: processor activation history (where current user was involved)
    processor_history = DelegationLog.objects.filter(
        performed_by=request.user
    ).filter(
        action__in=['activation_requested', 'activation_confirmed', 'activation_rejected']
    ).select_related('delegation', 'delegation__data_subject', 'delegation__proxy')[:50]

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'request_activation':
            # Request activation for an accepted delegation
            delegation_id = request.POST.get('delegation_id')
            reason = request.POST.get('reason', '').strip()

            # Get delegation - must be accepted status
            delegation = Delegation.objects.filter(
                id=delegation_id,
                status='accepted'
            ).first()

            if not delegation:
                messages.error(request, 'Invalid delegation selected.', extra_tags='danger')
                return redirect('users:activation_requests_view')

            if not reason:
                messages.error(request, 'Please provide a reason for activation.', extra_tags='danger')
                return redirect('users:activation_requests_view')

            # Check: already has pending activation?
            existing = DelegationActivation.objects.filter(
                delegation=delegation,
                status='pending'
            ).first()
            if existing:
                messages.error(request, 'An activation request is already pending for this delegation.', extra_tags='danger')
                return redirect('users:activation_requests_view')

            # Create activation request
            DelegationActivation.objects.create(
                delegation=delegation,
                initiated_by=request.user,
                reason=reason,
                status='pending'
            )

            # Log action
            DelegationLog.objects.create(
                delegation=delegation,
                action='activation_requested',
                performed_by=request.user,
                notes=reason
            )

            messages.success(request, 'Activation request submitted.')
            return redirect('users:activation_requests_view')

        elif action in ('confirm', 'reject'):
            # Confirm or reject a pending activation request
            activation_id = request.POST.get('activation_id')

            activation = DelegationActivation.objects.filter(
                id=activation_id,
                status='pending'
            ).select_related('delegation').first()

            if not activation:
                messages.error(request, 'Invalid activation request.', extra_tags='danger')
                return redirect('users:activation_requests_view')

            # Check: user cannot confirm/reject their own request
            if activation.initiated_by == request.user:
                messages.error(request, 'You cannot process your own activation request.', extra_tags='danger')
                return redirect('users:activation_requests_view')

            # Check: delegation still in accepted status
            if activation.delegation.status != 'accepted':
                messages.error(request, 'Delegation is no longer in accepted status.', extra_tags='danger')
                return redirect('users:activation_requests_view')

            if action == 'confirm':
                with transaction.atomic():
                    # Update delegation
                    activation.delegation.status = 'active'
                    activation.delegation.activated_at = timezone.now()
                    activation.delegation.save(update_fields=['status', 'activated_at'])

                    # Update activation
                    activation.status = 'confirmed'
                    activation.confirmed_by = request.user
                    activation.confirmed_at = timezone.now()
                    activation.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

                    # Log action
                    DelegationLog.objects.create(
                        delegation=activation.delegation,
                        action='activation_confirmed',
                        performed_by=request.user,
                        notes=f'Activation confirmed for {activation.delegation.proxy.get_full_name()}'
                    )

                messages.success(request, 'Delegation activated successfully.')

            elif action == 'reject':
                # Reject activation request
                activation.status = 'rejected'
                activation.confirmed_by = request.user
                activation.confirmed_at = timezone.now()
                activation.save(update_fields=['status', 'confirmed_by', 'confirmed_at'])

                # Log action
                DelegationLog.objects.create(
                    delegation=activation.delegation,
                    action='activation_rejected',
                    performed_by=request.user,
                    notes='Activation request rejected'
                )

                messages.success(request, 'Activation request rejected.')

            return redirect('users:activation_requests_view')

    return render(request, "users/activation_requests.html", {
        'accepted_delegations': accepted_delegations,
        'pending_activations': list(pending_activations),
        'pending_requests': pending_requests,
        'processor_history': processor_history,
    })