"""
Upgrading an existing database: the data migration must fill financial_year for
old invoices WITHOUT renumbering them or touching any other data.
Runs on a throw-away test database (TransactionTestCase).
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

BEFORE = [('store', '0018_order_total_igst_orderitem_igst_amount_product_igst_and_more')]
AFTER = [('store', '0021_alter_order_unique_together_financial_year')]


class FinancialYearMigrationTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        old_apps = executor.loader.project_state(BEFORE).apps
        User = old_apps.get_model('accounts', 'CustomUser')
        Customer = old_apps.get_model('store', 'ShopCustomer')
        Order = old_apps.get_model('store', 'Order')
        Product = old_apps.get_model('store', 'Product')
        owner = User.objects.create(phone='9000000001', email='o@x.com', username='shop1',
                                    dob=date(1990, 1, 1), location='Blr', password='x')
        cust = Customer.objects.create(store_owner=owner, phone='8000000001', name='Ramesh')
        Product.objects.create(store_owner=owner, purchased_from='IFFCO', purchase_date=date(2025, 4, 1),
                               purchase_invoice_number='P1', name='Urea', price=Decimal('300'), quantity=40)
        # Legacy global sequence spanning two financial years (+ one without invoice_date)
        rows = [(1, date(2026, 3, 31)), (2, date(2026, 4, 1)), (3, None)]
        for num, inv_date in rows:
            o = Order.objects.create(store_owner=owner, customer=cust, order_number=num,
                                     invoice_number=f'INV-{num:02d}', invoice_date=inv_date,
                                     total_price=Decimal('100'))
            if inv_date is None:   # order_date 31-Mar-2026 21:00 UTC = 1-Apr IST
                Order.objects.filter(pk=o.pk).update(order_date=datetime(2026, 3, 31, 21, 0, tzinfo=dt_timezone.utc))
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(AFTER)
        self.apps = executor.loader.project_state(AFTER).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def test_backfill_preserves_numbers_and_sets_year(self):
        Order = self.apps.get_model('store', 'Order')
        got = list(Order.objects.order_by('order_number').values_list('order_number', 'invoice_number', 'financial_year'))
        self.assertEqual(got, [(1, 'INV-01', 2025), (2, 'INV-02', 2026), (3, 'INV-03', 2026)])
        self.assertEqual(self.apps.get_model('store', 'Product').objects.get().quantity, 40)
        self.assertEqual(self.apps.get_model('store', 'ShopCustomer').objects.count(), 1)
