# bank/views.py - Bank Payment Management (independent of billing)

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import BankTransactionForm
from .models import BankTransaction


@login_required
def bank_payment_management(request):
    """List the store owner's bank transactions, show the balance, add new ones."""
    owner = request.user
    if request.method == 'POST':
        form = BankTransactionForm(request.POST)
        form.instance.store_owner = owner
        if form.is_valid():
            with transaction.atomic():
                txn = form.save()
            messages.success(
                request,
                f'{txn.get_transaction_type_display()} transaction of ₹{txn.amount} added.',
            )
            return redirect('bank_payment_management')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = BankTransactionForm()

    qs = BankTransaction.objects.filter(store_owner=owner)
    summary = qs.summary()

    # Running balance in chronological order, displayed newest first.
    rows, running = [], Decimal('0.00')
    for txn in qs.order_by('transaction_date', 'id'):
        running += txn.signed_amount
        rows.append({'txn': txn, 'running_balance': running})
    rows.reverse()

    return render(request, 'bank_payment_management.html', {
        'form': form,
        'rows': rows,
        'summary': summary,
        'store_owner': owner,
    })


@login_required
@require_POST
def delete_bank_transaction(request, pk):
    txn = get_object_or_404(BankTransaction, pk=pk, store_owner=request.user)
    txn.delete()
    messages.success(request, 'Bank transaction deleted.')
    return redirect('bank_payment_management')
