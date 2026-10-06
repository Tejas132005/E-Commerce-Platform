from django import forms
from django.utils import timezone

from .models import BankTransaction


class BankTransactionForm(forms.ModelForm):
    class Meta:
        model = BankTransaction
        fields = ['transaction_date', 'transaction_type', 'amount', 'transfer_direction', 'counterparty_account', 'description']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'transaction_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_transaction_type'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'transfer_direction': forms.Select(attrs={'class': 'form-select'}),
            'counterparty_account': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SBI Savings ****1234 / Cash in hand'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'e.g. Fertilizer supplier payment'}),
        }
        labels = {
            'transaction_date': 'Date',
            'transaction_type': 'Transaction Type',
            'transfer_direction': 'Transfer Direction',
            'counterparty_account': 'Other Account',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transaction_type'].choices = [('', 'Select type')] + BankTransaction.TRANSACTION_TYPE_CHOICES
        self.fields['transfer_direction'].choices = [('', 'Select direction')] + BankTransaction.TRANSFER_DIRECTION_CHOICES
        self.fields['transfer_direction'].required = False
        self.fields['counterparty_account'].required = False
        if not self.is_bound and not self.initial.get('transaction_date'):
            self.initial['transaction_date'] = timezone.localdate()
