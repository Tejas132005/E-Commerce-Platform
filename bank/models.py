# bank/models.py
#
# Bank Payment Management - fully independent of billing.
# No foreign keys to products, customers, orders or invoices; the only link is
# the store owner (each merchant sees only their own bank book).
#
# Balance rules (single bank account per store owner):
#   Credited              -> + amount   (money received into this account)
#   Debited               -> - amount   (money paid out: expense / payment)
#   Transferred, OUT      -> - amount   (moved to ANOTHER account you control, e.g. savings, cash)
#   Transferred, IN       -> + amount   (moved in FROM another account you control)
# A transfer is counted exactly once, in the direction it moved. It is kept separate
# from Credited/Debited so reports never mistake it for income or expense.

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, DecimalField, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import CustomUser

ZERO = Decimal('0.00')


class BankTransactionQuerySet(models.QuerySet):
    def signed_amount_expression(self):
        return Case(
            When(Q(transaction_type=BankTransaction.CREDITED), then='amount'),
            When(Q(transaction_type=BankTransaction.TRANSFERRED, transfer_direction=BankTransaction.TRANSFER_IN), then='amount'),
            When(Q(transaction_type=BankTransaction.DEBITED), then=-1 * models.F('amount')),
            When(Q(transaction_type=BankTransaction.TRANSFERRED, transfer_direction=BankTransaction.TRANSFER_OUT), then=-1 * models.F('amount')),
            default=Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )

    def balance(self):
        """Net balance of the transactions in this queryset."""
        dec = DecimalField(max_digits=14, decimal_places=2)
        return self.aggregate(total=Coalesce(Sum(self.signed_amount_expression(), output_field=dec), Value(ZERO), output_field=dec))['total']

    def summary(self):
        """Totals per kind, for the page header."""
        dec = DecimalField(max_digits=14, decimal_places=2)

        def total(**filters):
            return Coalesce(Sum('amount', filter=Q(**filters), output_field=dec), Value(ZERO), output_field=dec)

        data = self.aggregate(
            credited=total(transaction_type=BankTransaction.CREDITED),
            debited=total(transaction_type=BankTransaction.DEBITED),
            transferred_out=total(transaction_type=BankTransaction.TRANSFERRED, transfer_direction=BankTransaction.TRANSFER_OUT),
            transferred_in=total(transaction_type=BankTransaction.TRANSFERRED, transfer_direction=BankTransaction.TRANSFER_IN),
        )
        data['balance'] = data['credited'] + data['transferred_in'] - data['debited'] - data['transferred_out']
        return data


class BankTransaction(models.Model):
    CREDITED = 'credited'
    DEBITED = 'debited'
    TRANSFERRED = 'transferred'
    TRANSACTION_TYPE_CHOICES = [
        (CREDITED, 'Credited'),
        (DEBITED, 'Debited'),
        (TRANSFERRED, 'Transferred'),
    ]

    TRANSFER_OUT = 'out'
    TRANSFER_IN = 'in'
    TRANSFER_DIRECTION_CHOICES = [
        (TRANSFER_OUT, 'Out - to another account'),
        (TRANSFER_IN, 'In - from another account'),
    ]

    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='bank_transactions')
    transaction_date = models.DateField(default=timezone.localdate)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Always positive; the transaction type decides the direction.',
    )
    description = models.TextField(help_text='Reason / details, e.g. "Fertilizer supplier payment"')
    transfer_direction = models.CharField(
        max_length=3,
        choices=TRANSFER_DIRECTION_CHOICES,
        blank=True,
        default='',
        help_text='Only for Transferred: did the money leave this account or come into it?',
    )
    counterparty_account = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text='Only for Transferred: the other account, e.g. "SBI Savings ****1234" or "Cash in hand"',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = BankTransactionQuerySet.as_manager()

    class Meta:
        ordering = ['-transaction_date', '-id']
        indexes = [models.Index(fields=['store_owner', 'transaction_date'])]

    def __str__(self):
        return f"{self.get_transaction_type_display()} ₹{self.amount} on {self.transaction_date} ({self.store_owner_id})"

    def clean(self):
        super().clean()
        if self.transaction_type == self.TRANSFERRED:
            if self.transfer_direction not in (self.TRANSFER_OUT, self.TRANSFER_IN):
                raise ValidationError({'transfer_direction': 'Choose whether the money was transferred out of or into this account.'})
        else:
            # Direction / counterparty only make sense for transfers.
            self.transfer_direction = ''
            self.counterparty_account = ''
        if self.description is not None:
            self.description = self.description.strip()
            if not self.description:
                raise ValidationError({'description': 'Please enter a description.'})

    @property
    def signed_amount(self):
        if self.transaction_type == self.CREDITED:
            return self.amount
        if self.transaction_type == self.DEBITED:
            return -self.amount
        if self.transaction_type == self.TRANSFERRED:
            return self.amount if self.transfer_direction == self.TRANSFER_IN else -self.amount
        return ZERO

    @property
    def is_inflow(self):
        return self.signed_amount > 0
