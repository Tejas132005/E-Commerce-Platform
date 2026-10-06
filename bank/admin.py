from django.contrib import admin

from .models import BankTransaction


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'store_owner', 'transaction_type', 'transfer_direction', 'amount', 'description')
    list_filter = ('transaction_type', 'transfer_direction', 'transaction_date')
    search_fields = ('description', 'counterparty_account')
