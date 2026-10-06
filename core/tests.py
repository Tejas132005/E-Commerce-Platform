"""Home page dashboard tests (separate test database, rolled back after each test)."""
from datetime import date, datetime, time
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.dashboard import build_home_dashboard, resolve_range
from store.models import OrderItem, SalesReport
from store.tests.helpers import make_customer, make_invoice, make_owner, make_product

TODAY = date(2026, 10, 6)


def sell(owner, customer, product, qty, amount, day, deleted=False):
    order = make_invoice(owner, customer, day)
    if deleted:
        order.is_deleted = True
        order.order_number = 1000000 + order.id
        order.save()
    OrderItem.objects.create(order=order, product=product, quantity=qty, item_price=product.price, total_price=Decimal(amount))
    SalesReport.objects.create(store_owner=owner, customer=customer, product=product, order=order, quantity=qty,
                               total_price=Decimal(amount),
                               sale_date=timezone.make_aware(datetime.combine(day, time(12))))
    return order


@mock.patch('core.dashboard.timezone.localdate', return_value=TODAY)
class HomeDashboardDataTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.c1 = make_customer(self.owner)
        self.c2 = make_customer(self.owner, phone='8000000002', name='Suresh')
        self.urea = make_product(self.owner, 'Urea')
        self.dap = make_product(self.owner, 'DAP', price='1350.00')
        sell(self.owner, self.c1, self.urea, 3, '945.00', date(2026, 10, 6))
        sell(self.owner, self.c1, self.dap, 2, '2835.00', date(2026, 10, 6))
        sell(self.owner, self.c2, self.urea, 5, '1575.00', date(2026, 10, 1))
        sell(self.owner, self.c2, self.urea, 9, '9999.00', date(2026, 10, 2), deleted=True)   # excluded
        sell(self.owner, self.c2, self.urea, 4, '1260.00', date(2026, 5, 1))                 # outside 30d, inside FY
        other = make_owner(phone='9000000002', username='shop2')                             # other tenant
        sell(other, make_customer(other, phone='8000000009'), make_product(other, 'Other'), 50, '50000', date(2026, 10, 6))

    def test_days_vs_quantity(self, _):
        d = build_home_dashboard(self.owner, '7')
        self.assertEqual(d['days'][0], '2026-09-30')
        self.assertEqual(d['days'][-1], '2026-10-06')
        self.assertEqual(len(d['quantity_sold']), 7)
        self.assertEqual(d['quantity_sold'][-1], 5)      # 3 + 2 today
        self.assertEqual(d['quantity_sold'][1], 5)       # 1 Oct
        self.assertEqual(d['totals']['quantity_sold'], 10)

    def test_items_vs_amount(self, _):
        d = build_home_dashboard(self.owner, '30')
        self.assertEqual(d['items']['names'], ['DAP', 'Urea'])
        self.assertEqual(d['items']['amount'], [2835.0, 2520.0])
        self.assertEqual(d['items']['quantity'], [2, 8])
        self.assertEqual(d['totals']['sold_amount'], 5355.0)

    def test_days_vs_invoices(self, _):
        d = build_home_dashboard(self.owner, '7')
        self.assertEqual(d['invoices'][-1], 2)
        self.assertEqual(d['invoices'][1], 1)
        self.assertEqual(d['totals']['invoices'], 3)     # deleted one not counted

    def test_financial_year_range(self, _):
        d = build_home_dashboard(self.owner, 'fy')
        self.assertEqual(d['range']['start'], '2026-04-01')
        self.assertEqual(d['totals']['quantity_sold'], 14)

    def test_customer_count(self, _):
        self.assertEqual(build_home_dashboard(self.owner)['customer_count'], 2)

    def test_version_changes_when_data_changes(self, _):
        v1 = build_home_dashboard(self.owner)['version']
        self.assertEqual(v1, build_home_dashboard(self.owner)['version'])
        sell(self.owner, self.c1, self.urea, 1, '315.00', TODAY)
        self.assertNotEqual(v1, build_home_dashboard(self.owner)['version'])

    def test_unknown_range_falls_back(self, _):
        self.assertEqual(resolve_range('banana', TODAY)[0], '30')


class HomeViewTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        make_customer(self.owner)
        make_customer(self.owner, phone='8000000002', name='Suresh')

    def test_anonymous_home(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Start your store')
        self.assertNotContains(resp, 'Platform Features')
        self.assertNotIn('dashboard', resp.context)

    def test_owner_home_shows_charts_and_customer_count(self):
        self.client.force_login(self.owner)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['customer_count'], 2)
        self.assertContains(resp, 'title="Total customers">2</span>', html=False)
        for canvas in ('qtyChart', 'itemsChart', 'invoiceChart'):
            self.assertContains(resp, f'id="{canvas}"')
        self.assertContains(resp, 'id="dashboard-data"')
        self.assertContains(resp, 'Bank Payment Management')
        self.assertNotContains(resp, 'Platform Features')

    def test_stats_endpoint(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('home_stats'), {'range': '7'})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['customer_count'], 2)
        self.assertEqual(len(body['days']), 7)
        self.assertIn('no-cache', resp.get('Cache-Control', ''))

    def test_stats_endpoint_requires_login(self):
        resp = self.client.get(reverse('home_stats'))
        self.assertEqual(resp.status_code, 302)
