"""
Old invoices that arrive without a financial year (loaddata / restore after migrate,
locally regenerated migrations) must not make numbering restart at 1.
Runs on Django's throw-away test database.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from store.invoice_repair import repair_financial_years
from store.models import Order, OrderItem, Product, ShopCustomer
from .helpers import make_customer, make_invoice, make_owner, make_product


class LegacyNullYearTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer(self.owner)

    def load_legacy(self, n, first_day=date(2026, 4, 1), start_number=1, owner=None):
        """Insert invoices exactly like a restored old DB: numbers set, financial_year NULL."""
        owner = owner or self.owner
        customer = self.customer if owner == self.owner else make_customer(owner, phone='8000000077')
        Order.objects.bulk_create([
            Order(store_owner=owner, customer=customer, order_number=i, invoice_number=f'INV-{i:02d}',
                  invoice_date=first_day + timedelta(days=(i - start_number) // 5), total_price=Decimal('100'))
            for i in range(start_number, start_number + n)
        ])
        self.assertTrue(Order.objects.filter(financial_year__isnull=True).exists())

    def test_new_invoice_continues_after_700_old_invoices(self):
        self.load_legacy(700)
        self.assertEqual(Order.next_invoice_sequence(self.owner, 2026), 701)   # read path, before repair
        new = make_invoice(self.owner, self.customer, date(2026, 10, 8))
        self.assertEqual((new.financial_year, new.order_number, new.invoice_number), (2026, 701, 'INV-701'))
        self.assertFalse(Order.objects.filter(financial_year__isnull=True).exists())

    def test_old_invoice_numbers_are_not_changed(self):
        self.load_legacy(700)
        before = dict(Order.objects.values_list('id', 'invoice_number'))
        make_invoice(self.owner, self.customer, date(2026, 10, 8))
        after = dict(Order.objects.filter(id__in=before).values_list('id', 'invoice_number'))
        self.assertEqual(before, after)

    def test_clashing_invoices_created_after_upgrade_move_after_old_ones(self):
        self.load_legacy(700)
        # Simulate the bug: new code created INV-01..INV-03 in FY 2026-27 next to the old 1..700
        clash = []
        for i in (1, 2, 3):
            o = Order.objects.create(store_owner=self.owner, customer=self.customer, order_number=99000 + i,
                                     total_price=Decimal('5'), invoice_date=date(2026, 10, 1))
            Order.objects.filter(pk=o.pk).update(order_number=i, invoice_number=f'INV-{i:02d}', financial_year=2026)
            clash.append(o.pk)
        Order.objects.filter(pk__in=Order.objects.filter(financial_year__isnull=True).values('pk')).update()
        report = Order.repair_financial_years(self.owner)
        self.assertEqual([m['new'] for m in report[0]['renumbered']], ['INV-701', 'INV-702', 'INV-703'])
        self.assertEqual(list(Order.objects.filter(pk__in=clash).order_by('pk').values_list('order_number', flat=True)),
                         [701, 702, 703])
        active = Order.objects.filter(financial_year=2026, is_deleted=False)
        self.assertEqual(active.count(), active.values('order_number').distinct().count())   # no duplicates
        self.assertEqual(make_invoice(self.owner, self.customer, date(2026, 10, 9)).order_number, 704)

    def test_old_global_numbering_across_two_years(self):
        self.load_legacy(5, first_day=date(2025, 6, 1), start_number=1)       # FY 2025-26: 1..5
        self.load_legacy(5, first_day=date(2026, 6, 1), start_number=6)       # FY 2026-27: 6..10 (old global seq)
        self.assertEqual(make_invoice(self.owner, self.customer, date(2026, 10, 1)).order_number, 11)
        self.assertEqual(make_invoice(self.owner, self.customer, date(2027, 4, 1)).order_number, 1)   # next FY resets
        self.assertEqual(set(Order.objects.values_list('financial_year', flat=True)), {2025, 2026, 2027})

    def test_dry_run_changes_nothing_and_command_applies(self):
        self.load_legacy(10)
        out = StringIO()
        call_command('repair_invoice_numbers', '--dry-run', stdout=out)
        self.assertIn('10 old invoice(s)', out.getvalue())
        self.assertEqual(Order.objects.filter(financial_year__isnull=True).count(), 10)
        call_command('repair_invoice_numbers', stdout=StringIO())
        self.assertEqual(Order.objects.filter(financial_year__isnull=True).count(), 0)
        out = StringIO(); call_command('repair_invoice_numbers', stdout=out)
        self.assertIn('Nothing to repair', out.getvalue())

    def test_deleted_old_invoices_get_year_and_stay_parked(self):
        self.load_legacy(3)
        d = Order.objects.get(order_number=2)
        Order.objects.filter(pk=d.pk).update(is_deleted=True, order_number=1000000 + d.pk)
        Order.repair_financial_years()
        d.refresh_from_db()
        self.assertEqual((d.financial_year, d.order_number, d.is_deleted), (2026, 1000000 + d.pk, True))

    def test_other_store_owners_untouched_by_scoped_repair(self):
        other = make_owner(phone='9000000002', username='shop2')
        self.load_legacy(3)
        self.load_legacy(3, owner=other)
        Order.repair_financial_years(self.owner)
        self.assertEqual(Order.objects.filter(store_owner=other, financial_year__isnull=True).count(), 3)
        self.assertEqual(make_invoice(other, ShopCustomer.objects.get(store_owner=other), date(2026, 9, 1)).order_number, 4)

    def test_repair_does_not_touch_products_items_or_customers(self):
        product = make_product(self.owner, quantity=50)
        self.load_legacy(4)
        OrderItem.objects.create(order=Order.objects.first(), product=product, quantity=1,
                                 item_price=Decimal('300'), total_price=Decimal('315'))
        snap = lambda: (list(Product.objects.values()), list(ShopCustomer.objects.values()), list(OrderItem.objects.values()),
                        list(Order.objects.values_list('id', 'total_price', 'invoice_date', 'order_number')))
        before = snap()
        Order.repair_financial_years()
        self.assertEqual(snap(), before)

    def test_delete_flow_after_legacy_load_keeps_old_numbers_consistent(self):
        self.load_legacy(5)
        new = make_invoice(self.owner, self.customer, date(2026, 10, 1))        # -> 6, repair ran
        self.assertEqual(new.order_number, 6)
        Order.resequence_financial_year(self.owner, 2026)                     # existing delete/repair path
        self.assertEqual(sorted(Order.objects.filter(financial_year=2026).values_list('order_number', flat=True)),
                         [1, 2, 3, 4, 5, 6])
