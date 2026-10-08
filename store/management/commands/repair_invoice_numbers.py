"""
python manage.py repair_invoice_numbers --dry-run   # preview, changes nothing
python manage.py repair_invoice_numbers             # apply

Fills the financial year on old invoices that don't have one and moves any
invoice created after the upgrade that clashes with an old number (e.g. a
second INV-01 in FY 2026-27) to continue after the highest old number.
"""
from django.core.management.base import BaseCommand

from store.invoice_repair import format_report, repair_financial_years
from store.models import Order


class Command(BaseCommand):
    help = 'Give old invoices their financial year and fix invoice numbers that restarted at 1.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without saving.')
        parser.add_argument('--store-owner-id', type=int, help='Only repair this store owner.')

    def handle(self, *args, **opts):
        report = repair_financial_years(Order, store_owner_id=opts.get('store_owner_id'), dry_run=opts['dry_run'])
        self.stdout.write(format_report(report))
        if report:
            self.stdout.write(self.style.WARNING('DRY RUN - nothing saved.') if opts['dry_run']
                              else self.style.SUCCESS('Repair applied.'))
