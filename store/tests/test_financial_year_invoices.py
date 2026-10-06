"""
Financial-year (1 April - 31 March) invoice numbering.

All tests use Django's TestCase: they run against an automatically created,
separate test database and every test is rolled back afterwards.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from store.models import (
    Order, OrderItem, Product, SalesReport, ShopCustomer,
    financial_year_bounds, format_financial_year, get_financial_year,
)
from .helpers import (
    add_cart_line, login_customer, make_customer, make_invoice, make_owner, make_product,
)

FY_2025_26 = date(2025, 6, 1)
FY_2026_27 = date(2026, 6, 1)


class FinancialYearHelperTests(TestCase):
    def test_boundary_march_31_and_april_1(self):
        self.assertEqual(get_financial_year(date(2026, 3, 31)), 2025)   # FY 2025-26
        self.assertEqual(get_financial_year(date(2026, 4, 1)), 2026)    # FY 2026-27
        self.assertEqual(format_financial_year(2025), '2025-26')
        self.assertEqual(format_financial_year(2026), '2026-27')
        self.assertEqual(format_financial_year(2099), '2099-00')

    def test_january_belongs_to_previous_start_year(self):
        self.assertEqual(get_financial_year(date(2026, 1, 15)), 2025)
        self.assertEqual(financial_year_bounds(2025), (date(2025, 4, 1), date(2026, 3, 31)))

    def test_aware_datetime_uses_project_timezone(self):
        # 31 Mar 2026 20:00 UTC is already 1 Apr 2026 01:30 in Asia/Kolkata.
        utc_dt = datetime(2026, 3, 31, 20, 0, tzinfo=dt_timezone.utc)
        self.assertEqual(get_financial_year(utc_dt), 2026)

    def test_defaults_to_today(self):
        with mock.patch('store.models.timezone.localdate', return_value=date(2027, 4, 1)):
            self.assertEqual(get_financial_year(), 2027)


class InvoiceNumberingTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer(self.owner)

    # Test 1 + "no existing invoices" edge case
    def test_first_invoice_of_financial_year_is_1(self):
        self.assertFalse(Order.objects.exists())
        order = make_invoice(self.owner, self.customer, FY_2025_26)
        self.assertEqual(order.order_number, 1)
        self.assertEqual(order.invoice_number, 'INV-01')
        self.assertEqual(order.financial_year, 2025)
        self.assertEqual(order.financial_year_label, '2025-26')

    # Test 2
    def test_sequential_invoices_within_year(self):
        numbers = [make_invoice(self.owner, self.customer, FY_2025_26).order_number for _ in range(5)]
        self.assertEqual(numbers, [1, 2, 3, 4, 5])

    # Test 3
    def test_numbering_resets_in_new_financial_year(self):
        for _ in range(3):
            make_invoice(self.owner, self.customer, FY_2025_26)
        first_new = make_invoice(self.owner, self.customer, FY_2026_27)
        self.assertEqual(first_new.order_number, 1)          # not 4
        self.assertEqual(first_new.invoice_number, 'INV-01')
        self.assertEqual(first_new.financial_year, 2026)
        self.assertEqual(make_invoice(self.owner, self.customer, FY_2026_27).order_number, 2)

    # Test 4
    def test_previous_year_invoices_remain(self):
        old1 = make_invoice(self.owner, self.customer, FY_2025_26)
        old2 = make_invoice(self.owner, self.customer, FY_2025_26)
        new1 = make_invoice(self.owner, self.customer, FY_2026_27)
        self.assertEqual(Order.objects.count(), 3)
        for order, fy, num in [(old1, 2025, 1), (old2, 2025, 2), (new1, 2026, 1)]:
            order.refresh_from_db()
            self.assertEqual((order.financial_year, order.order_number), (fy, num))
        # Old invoice still opens on the owner's invoice pages
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('generate_invoice_view', args=[self.owner.username, old1.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'INV-01')
        self.assertContains(resp, 'FY: 2025-26')

    def test_boundary_dates_pick_correct_year(self):
        a = make_invoice(self.owner, self.customer, date(2026, 3, 31))
        b = make_invoice(self.owner, self.customer, date(2026, 4, 1))
        self.assertEqual((a.financial_year, a.order_number), (2025, 1))
        self.assertEqual((b.financial_year, b.order_number), (2026, 1))

    def test_multiple_years_each_start_at_1_without_conflict(self):
        for d in [date(2024, 7, 1), date(2025, 7, 1), date(2026, 7, 1)]:
            self.assertEqual(make_invoice(self.owner, self.customer, d).order_number, 1)
        self.assertEqual(
            sorted(Order.objects.values_list('financial_year', 'order_number')),
            [(2024, 1), (2025, 1), (2026, 1)],
        )

    def test_backdated_invoice_continues_its_own_year(self):
        make_invoice(self.owner, self.customer, FY_2025_26)
        make_invoice(self.owner, self.customer, FY_2026_27)
        late_entry = make_invoice(self.owner, self.customer, date(2026, 3, 20))
        self.assertEqual((late_entry.financial_year, late_entry.order_number), (2025, 2))

    def test_invoice_without_invoice_date_uses_today(self):
        with mock.patch('store.models.timezone.localdate', return_value=date(2027, 4, 1)):
            order = make_invoice(self.owner, self.customer, None)
        self.assertEqual((order.financial_year, order.order_number), (2027, 1))

    def test_numbering_is_per_store_owner(self):
        other = make_owner(phone='9000000002', username='shop2')
        other_customer = make_customer(other, phone='8000000002')
        make_invoice(self.owner, self.customer, FY_2026_27)
        self.assertEqual(make_invoice(other, other_customer, FY_2026_27).order_number, 1)

    def test_duplicate_number_in_same_year_rejected_by_db(self):
        make_invoice(self.owner, self.customer, FY_2025_26)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=make_invoice(self.owner, self.customer, FY_2025_26).pk).update(order_number=1)

    def test_same_number_in_different_years_allowed(self):
        a = make_invoice(self.owner, self.customer, FY_2025_26)
        b = make_invoice(self.owner, self.customer, FY_2026_27)
        self.assertEqual(a.order_number, b.order_number)
        self.assertEqual(a.invoice_number, b.invoice_number)
        self.assertNotEqual(a.financial_year, b.financial_year)

    def test_save_with_update_fields_keeps_working(self):
        order = make_invoice(self.owner, self.customer, FY_2025_26)
        order.status = 'confirmed'
        order.save(update_fields=['status'])
        order.refresh_from_db()
        self.assertEqual((order.status, order.order_number, order.financial_year), ('confirmed', 1, 2025))


class CheckoutAcrossFinancialYearsTests(TestCase):
    """End-to-end through the real checkout view (cart -> order, stock, sales report)."""

    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer(self.owner)
        self.other_customer = make_customer(self.owner, phone='8000000099', name='Suresh')
        self.urea = make_product(self.owner, 'Urea 45kg', quantity=100)
        self.dap = make_product(self.owner, 'DAP 50kg', quantity=50, price='1350.00', gst='5.00')
        login_customer(self.client, self.owner, self.customer)

    def checkout(self, product, qty, day):
        add_cart_line(self.owner, self.customer, product, qty, day)
        resp = self.client.post(reverse('checkout', args=[self.owner.username]))
        self.assertEqual(resp.status_code, 302)
        return Order.objects.latest('id')

    def test_checkout_numbers_reset_on_april_1(self):
        o1 = self.checkout(self.urea, 2, date(2026, 3, 30))
        o2 = self.checkout(self.urea, 1, date(2026, 3, 31))
        o3 = self.checkout(self.dap, 1, date(2026, 4, 1))
        self.assertEqual([(o.financial_year, o.invoice_number) for o in (o1, o2, o3)],
                         [(2025, 'INV-01'), (2025, 'INV-02'), (2026, 'INV-01')])

    # Test 5
    def test_products_and_stock_carry_over(self):
        before = {p.pk: (p.name, p.price, p.initial_stock, p.gst) for p in Product.objects.all()}
        self.checkout(self.urea, 10, date(2026, 3, 31))
        self.checkout(self.urea, 5, date(2026, 4, 1))   # new financial year
        self.assertEqual(Product.objects.count(), 2)
        after = {p.pk: (p.name, p.price, p.initial_stock, p.gst) for p in Product.objects.all()}
        self.assertEqual(before, after)                  # nothing reset / deleted
        self.urea.refresh_from_db(); self.dap.refresh_from_db()
        self.assertEqual(self.urea.quantity, 85)         # only reduced by sales
        self.assertEqual(self.dap.quantity, 50)
        self.assertEqual(OrderItem.objects.count(), 2)
        self.assertEqual(SalesReport.objects.count(), 2)

    # Test 6
    def test_customers_carry_over(self):
        self.checkout(self.urea, 1, date(2026, 3, 31))
        self.checkout(self.urea, 1, date(2026, 4, 1))
        self.assertEqual(ShopCustomer.objects.count(), 2)
        self.assertEqual(set(ShopCustomer.objects.values_list('name', flat=True)), {'Ramesh', 'Suresh'})
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 2)

    def test_gst_totals_unchanged_by_numbering(self):
        order = self.checkout(self.urea, 2, date(2026, 4, 1))
        self.assertEqual(order.subtotal, Decimal('600.00'))
        self.assertEqual(order.total_gst, Decimal('30.00'))
        self.assertEqual(order.total_price, Decimal('630.00'))


class DeleteRestoreRepairPerYearTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer(self.owner)
        self.old = [make_invoice(self.owner, self.customer, date(2026, 3, d)) for d in (1, 2, 3)]
        self.new = [make_invoice(self.owner, self.customer, date(2026, 4, d)) for d in (1, 2, 3)]
        login_customer(self.client, self.owner, self.customer)

    def numbers(self, fy):
        return list(Order.objects.filter(financial_year=fy, is_deleted=False)
                    .order_by('order_number').values_list('order_number', 'invoice_number'))

    def test_delete_resequences_only_that_year(self):
        self.client.post(reverse('delete_invoice', args=[self.owner.username, self.new[0].id]))
        self.assertEqual(self.numbers(2026), [(1, 'INV-01'), (2, 'INV-02')])
        self.assertEqual(self.numbers(2025), [(1, 'INV-01'), (2, 'INV-02'), (3, 'INV-03')])

    def test_restore_takes_next_number_in_its_own_year(self):
        self.client.post(reverse('delete_invoice', args=[self.owner.username, self.old[1].id]))
        self.client.post(reverse('restore_invoice', args=[self.owner.username, self.old[1].id]))
        restored = Order.objects.get(pk=self.old[1].pk)
        self.assertEqual((restored.financial_year, restored.order_number, restored.invoice_number), (2025, 3, 'INV-03'))
        self.assertEqual(self.numbers(2026), [(1, 'INV-01'), (2, 'INV-02'), (3, 'INV-03')])

    def test_repair_sequence_restarts_each_year(self):
        # Simulate legacy data: FY 2026-27 continued the old global sequence (4, 5, 6).
        for i, o in enumerate(self.new, start=4):
            Order.objects.filter(pk=o.pk).update(order_number=i, invoice_number=f'INV-{i:02d}')
        self.client.force_login(self.owner)
        self.client.get(reverse('repair_sequence'))
        self.assertEqual(self.numbers(2026), [(1, 'INV-01'), (2, 'INV-02'), (3, 'INV-03')])
        self.assertEqual(self.numbers(2025), [(1, 'INV-01'), (2, 'INV-02'), (3, 'INV-03')])

    def test_all_invoices_lists_every_year_and_searches_by_fy(self):
        self.client.force_login(self.owner)
        url = reverse('all_invoices', args=[self.owner.username])
        resp = self.client.get(url)
        self.assertEqual(len(resp.context['orders']), 6)
        self.assertContains(resp, 'FY 2025-26')
        self.assertContains(resp, 'FY 2026-27')
        resp = self.client.get(url, {'q': '2025-26'})
        self.assertEqual({o.financial_year for o in resp.context['orders']}, {2025})
