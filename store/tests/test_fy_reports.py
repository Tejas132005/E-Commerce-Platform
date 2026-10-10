"""
Financial-year purchase / sales / inventory reporting (store/fy_reports.py) and the pages using it.
All tests run on Django's separate test database and are rolled back automatically.
"""
from datetime import date, datetime, time
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from bank.models import BankTransaction
from store import fy_reports as R
from store.models import (Order, OrderItem, Product, ProductReturn, SalesReport, ShopCustomer,
                          format_invoice_number, get_financial_year)
from .helpers import make_customer, make_owner

D = Decimal


# ------------------------------------------------------------------ factories

def lot(owner, name, qty, cost, day, category='Fertilizer', gst='0', igst='0', unit_amount='0'):
    """A purchase lot exactly as Add Product stores it (initial_stock = quantity on creation)."""
    return Product.objects.create(
        store_owner=owner, purchased_from='IFFCO', purchase_date=day, purchase_invoice_number=f'P-{name}',
        name=name, price=D(cost), quantity=qty, category=category, gst=D(gst), igst=D(igst),
        taxable_unit_amount=D(cost), unit_amount=D(unit_amount))


def sell(owner, customer, product, qty, unit_price, day, gst='0'):
    """An invoice the way checkout writes it: Order + OrderItem + SalesReport, stock reduced."""
    sub = D(unit_price) * qty
    tax = (sub * D(gst) / 100).quantize(D('0.01'))
    order = Order.objects.create(store_owner=owner, customer=customer, total_price=sub + tax, subtotal=sub,
                                 total_gst=tax, total_cgst=tax / 2, total_sgst=tax / 2, invoice_date=day)
    order.invoice_number = format_invoice_number(order.order_number)
    order.save()
    OrderItem.objects.create(order=order, product=product, quantity=qty, item_price=D(unit_price), total_price=sub + tax,
                             subtotal=sub, cgst_amount=tax / 2, sgst_amount=tax / 2, gst_amount=tax, igst_amount=D('0'))
    SalesReport.objects.create(store_owner=owner, customer=customer, product=product, order=order, quantity=qty,
                               total_price=sub + tax, category=product.category,
                               sale_date=timezone.make_aware(datetime.combine(day, time(12))))
    Product.objects.filter(pk=product.pk).update(quantity=product.quantity - qty)
    product.refresh_from_db()
    return order


def supplier_return(product, qty, day):
    cost = product.taxable_unit_amount
    r = ProductReturn.objects.create(
        purchase_invoice_number=product.purchase_invoice_number, product=product, returned_invoice_number='R-1',
        stock_returned=qty, current_stock=product.quantity - qty, return_date=day, taxable_unit_amount=cost,
        gst=product.gst, taxable_total_amount=cost * qty, total_amount=cost * qty)
    Product.objects.filter(pk=product.pk).update(quantity=product.quantity - qty)
    product.refresh_from_db()
    return r


def snapshot():
    """Every row of every business table, for 'nothing changed' assertions."""
    return {m.__name__: list(m.objects.order_by('pk').values())
            for m in (Product, Order, OrderItem, SalesReport, ProductReturn, ShopCustomer, CustomUser, BankTransaction)}


# ------------------------------------------------------------------ Test F: boundaries

class FinancialYearBoundaryTests(TestCase):
    def test_boundary_dates(self):
        self.assertEqual(get_financial_year(date(2026, 3, 31)), 2025)
        self.assertEqual(get_financial_year(date(2026, 4, 1)), 2026)
        self.assertEqual(get_financial_year(date(2027, 3, 31)), 2026)
        self.assertEqual(get_financial_year(date(2027, 4, 1)), 2027)

    def test_transactions_split_at_boundary(self):
        owner = make_owner(); c = make_customer(owner)
        a = lot(owner, 'A', 10, '100', date(2026, 3, 31))
        b = lot(owner, 'B', 10, '100', date(2026, 4, 1))
        sell(owner, c, b, 1, '150', date(2027, 3, 31))
        sell(owner, c, b, 2, '150', date(2027, 4, 1))
        self.assertEqual(R.purchase_report(owner, 2025)['totals']['gross'], D('1000.00'))
        self.assertEqual(R.purchase_report(owner, 2026)['totals']['gross'], D('1000.00'))
        self.assertEqual(R.sales_report(owner, 2026)['totals']['quantity'], 1)
        self.assertEqual(R.sales_report(owner, 2027)['totals']['quantity'], 2)
        self.assertEqual(R.opening_inventory(owner, 2026)['quantity'], 10)      # A carried into FY 2026-27
        self.assertEqual(R.opening_inventory(owner, 2027)['quantity'], 19)      # A 10 + B 10 - 1 sold on 31 Mar

    def test_resolve_and_choices(self):
        with mock.patch('store.fy_reports.timezone.localdate', return_value=date(2026, 10, 1)):
            self.assertEqual(R.resolve_fy('2024'), 2024)
            self.assertEqual(R.resolve_fy('fy2025'), 2025)
            self.assertEqual(R.resolve_fy('2030'), 2026)       # future -> current
            self.assertEqual(R.resolve_fy('x'), 2026)
            self.assertEqual(R.fy_choices()[0], (2026, 'FY 2026-27'))
            self.assertEqual(len(R.fy_choices()), 11)


# ------------------------------------------------------------------ Test A: month-wise purchases

class MonthlyPurchaseTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        lot(self.owner, 'Apr', 10, '100', date(2026, 4, 5))                  # 1,000
        lot(self.owner, 'Apr2', 5, '200', date(2026, 4, 28), gst='5')         # 1,000 + 5% = 1,050
        lot(self.owner, 'Jun', 3, '1000', date(2026, 6, 15))                  # 3,000
        lot(self.owner, 'Mar', 1, '700', date(2027, 3, 31))                   # 700 (last day of FY)
        lot(self.owner, 'Before', 99, '100', date(2026, 3, 31))               # previous FY - excluded
        lot(self.owner, 'After', 99, '100', date(2027, 4, 1))                 # next FY - excluded

    def test_twelve_months_in_fy_order_with_zeros(self):
        monthly = R.purchase_report(self.owner, 2026)['monthly']
        self.assertEqual([m['month'] for m in monthly],
                         ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar'])
        values = {m['month']: m['gross'] for m in monthly}
        self.assertEqual(values['Apr'], D('2050.00'))
        self.assertEqual(values['Jun'], D('3000.00'))
        self.assertEqual(values['Mar'], D('700.00'))
        self.assertEqual(values['May'], D('0.00'))
        self.assertEqual(sum(values.values()), D('5750.00'))

    def test_out_of_year_purchases_excluded_from_totals(self):
        totals = R.purchase_report(self.owner, 2026)['totals']
        self.assertEqual((totals['lots'], totals['taxable'], totals['gross']), (4, D('5700.00'), D('5750.00')))

    def test_existing_unit_amount_rule_is_reused(self):
        # Existing purchase reports prefer unit_amount over taxable_unit_amount when it is set.
        lot(self.owner, 'AD', 2, '100', date(2026, 8, 1), unit_amount='120')
        self.assertEqual({m['month']: m['gross'] for m in R.purchase_report(self.owner, 2026)['monthly']}['Aug'], D('240.00'))

    def test_igst_lot(self):
        lot(self.owner, 'IG', 10, '100', date(2026, 9, 1), igst='18')
        self.assertEqual({m['month']: m['gross'] for m in R.purchase_report(self.owner, 2026)['monthly']}['Sep'], D('1180.00'))


# ------------------------------------------------------------------ Test B: summary + formatting

class SummaryAndFormattingTests(TestCase):
    def test_indian_currency_format(self):
        self.assertEqual(R.format_inr(D('500000')), '₹5,00,000.00')
        self.assertEqual(R.format_inr(D('12345678.5')), '₹1,23,45,678.50')
        self.assertEqual(R.format_inr(D('999')), '₹999.00')

    def test_difference_rules(self):
        # Sales − Purchase: purchase 5L / sales 3L -> red '−2L'; purchase 3L / sales 5L -> green '+2L'
        self.assertEqual(R.difference_display(D('500000'), D('300000')),
                         {'value': D('-200000.00'), 'text': '\u2212₹2,00,000.00', 'tone': 'purchase-higher'})
        self.assertEqual(R.difference_display(D('300000'), D('500000')),
                         {'value': D('200000.00'), 'text': '+₹2,00,000.00', 'tone': 'sales-higher'})
        self.assertEqual(R.difference_display(D('500000'), D('500000')),
                         {'value': D('0.00'), 'text': '₹0.00', 'tone': 'neutral'})

    def test_summary_values_and_update(self):
        owner = make_owner(); c = make_customer(owner)
        p = lot(owner, 'Urea', 100, '300', date(2026, 5, 1), gst='5')          # 31,500 incl. GST
        sell(owner, c, p, 10, '400', date(2026, 6, 1), gst='5')                 # 4,200 incl. GST
        s = R.fy_summary(owner, 2026)
        self.assertEqual((s['purchase']['gross'], s['sales']['gross']), (D('31500.00'), D('4200.00')))
        self.assertEqual((s['difference']['text'], s['difference']['tone']), ('\u2212₹27,300.00', 'purchase-higher'))
        sell(owner, c, p, 80, '450', date(2026, 7, 1), gst='5')                 # +37,800
        s = R.fy_summary(owner, 2026)
        self.assertEqual(s['sales']['gross'], D('42000.00'))
        self.assertEqual((s['difference']['text'], s['difference']['tone']), ('+₹10,500.00', 'sales-higher'))


@mock.patch('core.dashboard.timezone.localdate', return_value=date(2026, 10, 6))
class HomePageFyWidgetsTests(TestCase):
    """Test B + C on the real home page and its live-update endpoint."""

    def setUp(self):
        self.owner = make_owner()
        self.c = make_customer(self.owner)
        self.p = lot(self.owner, 'DAP', 100, '1000', date(2026, 4, 10), category='Phosphate')     # 1,00,000
        sell(self.owner, self.c, self.p, 20, '1200', date(2026, 5, 2))                             # 24,000
        lot(self.owner, 'Old', 50, '100', date(2025, 6, 1), category='Potash')                     # FY 2025-26
        self.client.force_login(self.owner)

    def test_boxes_render_with_colours_and_links(self, _):
        html = self.client.get('/', {'range': 'fy'}).content.decode()
        self.assertIn('₹1,00,000.00', html)
        self.assertIn('₹24,000.00', html)
        self.assertIn('tone-purchase-higher">\u2212₹76,000.00', html)     # Sales − Purchase: sales lower -> red '−'
        self.assertIn(reverse('fy_analytics', args=['purchases']) + '?fy=2026', html)
        self.assertIn(reverse('fy_analytics', args=['sales']) + '?fy=2026', html)
        self.assertIn('id="purchaseMonthChart"', html)

    def test_short_ranges_use_current_fy_and_past_fy_follows_selector(self, _):
        self.assertEqual(self.client.get('/core/home-stats/', {'range': '7'}).json()['fy_summary']['fy'], 2026)
        past = self.client.get('/core/home-stats/', {'range': 'fy2025'}).json()['fy_summary']
        self.assertEqual((past['fy'], past['label'], past['purchase']['text']), (2025, 'FY 2025-26', '₹5,000.00'))
        self.assertEqual(past['monthly_purchases'][2], 5000.0)          # June

    def test_values_update_and_version_changes_on_new_purchase(self, _):
        before = self.client.get('/core/home-stats/', {'range': 'fy'}).json()
        lot(self.owner, 'MOP', 10, '1700', date(2026, 10, 1), category='Potash')
        after = self.client.get('/core/home-stats/', {'range': 'fy'}).json()
        self.assertNotEqual(before['version'], after['version'])
        self.assertEqual(after['fy_summary']['purchase']['text'], '₹1,17,000.00')
        self.assertEqual(after['fy_summary']['monthly_purchases'][6], 17000.0)   # October


# ------------------------------------------------------------------ Test C + D: analytics pages

@mock.patch('store.fy_reports.timezone.localdate', return_value=date(2026, 10, 6))
class AnalyticsPagesTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        c = make_customer(self.owner)
        self.urea = lot(self.owner, 'Urea', 100, '300', date(2026, 4, 2), category='Nitrogen', gst='5')
        self.dap = lot(self.owner, 'DAP', 50, '1300', date(2026, 5, 2), category='Phosphate', gst='5')
        self.npk = lot(self.owner, 'NPK', 20, '1400', date(2026, 6, 2), category='Phosphate', gst='5')
        self.blank = lot(self.owner, 'Neem', 10, '50', date(2026, 6, 3), category='')
        sell(self.owner, c, self.urea, 10, '350', date(2026, 6, 1), gst='5')
        sell(self.owner, c, self.dap, 5, '1500', date(2026, 7, 1), gst='5')
        deleted = sell(self.owner, c, self.npk, 3, '1600', date(2026, 7, 2), gst='5')
        Order.objects.filter(pk=deleted.pk).update(is_deleted=True, order_number=1000000 + deleted.pk)
        lot(self.owner, 'Older', 10, '999', date(2026, 3, 1), category='Nitrogen')          # previous FY
        other = make_owner(phone='9000000002', username='shop2')
        lot(other, 'Theirs', 999, '999', date(2026, 5, 1))                                     # other tenant
        self.client.force_login(self.owner)

    def test_purchase_page(self, _):
        resp = self.client.get(reverse('fy_analytics', args=['purchases']), {'fy': '2026'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['fy'], 2026)
        rep = resp.context['report']
        cats = {c['category']: c for c in rep['categories']}
        self.assertEqual(set(cats), {'Nitrogen', 'Phosphate', 'Uncategorized'})
        self.assertEqual(cats['Phosphate']['gross'], D('97650.00'))     # (65,000 + 28,000) x 1.05
        self.assertEqual(cats['Phosphate']['products'], 2)
        self.assertEqual(cats['Nitrogen']['quantity'], 100)               # 'Older' (FY 2025-26) excluded
        self.assertEqual(rep['totals']['gross'], D('129650.00'))   # 31,500 + 97,650 + 500
        self.assertNotContains(resp, 'Theirs')

    def test_sales_page_no_double_count_and_deleted_excluded(self, _):
        resp = self.client.get(reverse('fy_analytics', args=['sales']), {'fy': '2026'})
        rep = resp.context['report']
        items = {i['name']: i for i in rep['items']}
        self.assertEqual(set(items), {'Urea', 'DAP'})                    # deleted NPK invoice excluded
        self.assertEqual(items['Urea']['gross'], D('3675.00'))             # once, not OrderItem + SalesReport
        self.assertEqual(items['DAP']['taxable'], D('7500.00'))
        self.assertEqual(rep['totals']['gross'], D('11550.00'))
        self.assertEqual(rep['totals']['invoices'], 2)

    def test_historical_prices_respected(self, _):
        Product.objects.filter(pk=self.urea.pk).update(price=D('9999'))   # selling price changed later
        self.assertEqual({i['name']: i for i in R.sales_report(self.owner, 2026)['items']}['Urea']['gross'], D('3675.00'))

    def test_compare_page(self, _):
        resp = self.client.get(reverse('fy_analytics', args=['compare']), {'fy': '2026'})
        rows = {r['category']: r for r in resp.context['comparison']}
        self.assertEqual(rows['Phosphate']['purchase'], D('97650.00'))
        self.assertEqual(rows['Phosphate']['sales'], D('7875.00'))
        self.assertEqual(rows['Phosphate']['difference']['tone'], 'purchase-higher')
        self.assertContains(resp, 'not profit')
        self.assertIn('rollforward', resp.context)

    def test_unknown_kind_404_and_login_required(self, _):
        self.assertEqual(self.client.get('/store/fy-analytics/nope/').status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('fy_analytics', args=['sales'])).status_code, 302)

    def test_default_is_current_fy(self, _):
        self.assertEqual(self.client.get(reverse('fy_analytics', args=['sales'])).context['fy'], 2026)


# ------------------------------------------------------------------ Test E: Avg Revenue/Items

@mock.patch('store.fy_reports.timezone.localdate', return_value=date(2026, 10, 6))
class AvgRevenuePerItemTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        c = make_customer(self.owner)
        a = lot(self.owner, 'A', 100, '100', date(2026, 4, 2), category='X')
        lot(self.owner, 'Unsold', 100, '100', date(2026, 4, 2), category='X')
        sell(self.owner, c, a, 4, '250', date(2026, 5, 1))        # 1,000 for 4 items
        sell(self.owner, c, a, 1, '500', date(2025, 5, 1))        # FY 2025-26
        self.client.force_login(self.owner)

    def test_labels_changed(self, _):
        for name in ('analytics_dashboard.html', 'user_analytics_dashboard.html'):
            with open(settings.BASE_DIR / 'templates' / name, encoding='utf-8') as f:
                text = f.read()
            self.assertIn('Avg Revenue/Items', text)
            self.assertNotIn('Avg Revenue/Product', text)

    def test_revenue_divided_by_quantity_sold(self, _):
        body = self.client.get(f'/store/{self.owner.username}/analytics/items/', {'fy': '2026'}).json()
        self.assertEqual(body['summary']['total_items_sold'], 4)
        self.assertEqual(body['summary']['average_revenue_per_item'], 250.0)     # not 1,000 / 2 products
        self.assertEqual(body['financial_year'], 'FY 2026-27')
        allt = self.client.get(f'/store/{self.owner.username}/analytics/items/', {'fy': 'all'}).json()
        self.assertEqual((allt['summary']['total_items_sold'], allt['summary']['average_revenue_per_item']), (5, 300.0))
        cats = self.client.get(f'/store/{self.owner.username}/analytics/categories/', {'fy': '2026'}).json()
        self.assertEqual(cats['categories'][0]['average_revenue_per_item'], 250.0)

    def test_zero_quantity_is_safe(self, _):
        body = self.client.get(f'/store/{self.owner.username}/analytics/items/', {'fy': '2020'}).json()
        self.assertEqual(body['status'], 'success')
        self.assertEqual(body['summary']['average_revenue_per_item'], 0)

    def test_sales_dashboard_follows_fy(self, _):
        resp = self.client.get('/store/sales-dashboard/', {'fy': '2026'})
        self.assertEqual(resp.context['total_sales'], D('1000.00'))
        self.assertEqual(self.client.get('/store/sales-dashboard/', {'fy': 'all'}).context['total_sales'], D('1500.00'))


# ------------------------------------------------------------------ Test G / H / I: opening stock

class OpeningInventoryCarryForwardTests(TestCase):
    """
    FY 2025-26 leaves 50 units of lot A (cost 1,000) = 50,000 as opening stock of FY 2026-27.
    FY 2026-27 purchases 8,00,000; sales leave lot C 100 x 2,000 = 2,00,000.
    FY 2027-28 must open with 2,00,000, count its own 5,00,000 purchases separately, etc.
    Everything below is derived from stock movements (lots, invoices), not typed-in totals.
    """

    def setUp(self):
        self.owner = make_owner()
        self.c = make_customer(self.owner)
        self.a = lot(self.owner, 'A', 100, '1000', date(2026, 2, 1))                # FY 2025-26: 1,00,000
        sell(self.owner, self.c, self.a, 50, '1200', date(2026, 3, 15))              # leaves 50 x 1,000
        self.b = lot(self.owner, 'B', 400, '1000', date(2026, 5, 1))                 # FY 2026-27: 4,00,000
        self.cc = lot(self.owner, 'C', 200, '2000', date(2026, 9, 1))                # FY 2026-27: 4,00,000
        sell(self.owner, self.c, self.a, 50, '1200', date(2026, 6, 1))               # A cleared (cost 50,000)
        sell(self.owner, self.c, self.b, 400, '1200', date(2026, 11, 1))             # B cleared (cost 4,00,000)
        sell(self.owner, self.c, self.cc, 100, '2500', date(2027, 1, 15))            # C: 100 left (cost 2,00,000 sold)
        self.d = lot(self.owner, 'D', 250, '2000', date(2027, 5, 1))                 # FY 2027-28: 5,00,000
        sell(self.owner, self.c, self.cc, 50, '2500', date(2027, 6, 1))              # FY 2027-28 sales 1,25,000

    def test_fy_2026_27_opening_purchases_closing(self):
        self.assertEqual(R.opening_inventory(self.owner, 2026)['value'], D('50000.00'))
        self.assertEqual(R.purchase_report(self.owner, 2026)['totals']['gross'], D('800000.00'))
        roll = R.inventory_rollforward(self.owner, 2026, today=date(2027, 6, 30))
        self.assertEqual(roll['cogs'], D('650000.00'))
        self.assertEqual(roll['closing']['value'], D('200000.00'))
        self.assertEqual(roll['closing']['quantity'], 100)
        self.assertTrue(roll['balanced'])

    def test_fy_2027_28_opens_with_previous_closing_and_keeps_purchases_separate(self):
        opening = R.opening_inventory(self.owner, 2027)
        self.assertEqual((opening['value'], opening['quantity'], opening['lots']), (D('200000.00'), 100, 1))
        purchases = R.purchase_report(self.owner, 2027)['totals']
        self.assertEqual(purchases['gross'], D('500000.00'))          # not 7,00,000 and not 13,00,000
        self.assertEqual(R.sales_report(self.owner, 2027)['totals']['gross'], D('125000.00'))
        summary = R.fy_summary(self.owner, 2027)
        self.assertEqual(summary['purchase']['gross'], D('500000.00'))   # sales never added to purchases
        self.assertEqual(summary['opening_stock']['value'], D('200000.00'))
        roll = R.inventory_rollforward(self.owner, 2027, today=date(2028, 4, 10))
        self.assertEqual(roll['closing']['value'], D('600000.00'))      # 2,00,000 - 1,00,000 + 5,00,000
        self.assertTrue(roll['balanced'])

    def test_closing_equals_next_opening(self):
        for fy in (2025, 2026):
            closing = R.closing_inventory(self.owner, fy, today=date(2028, 4, 10))
            self.assertEqual(closing['value'], R.opening_inventory(self.owner, fy + 1)['value'])

    def test_valued_at_cost_never_selling_price(self):
        Product.objects.filter(pk=self.cc.pk).update(price=D('99999'))
        self.assertEqual(R.opening_inventory(self.owner, 2027)['value'], D('200000.00'))

    def test_supplier_return_reduces_stock_not_purchases(self):
        supplier_return(self.cc, 10, date(2027, 2, 1))
        self.assertEqual(R.opening_inventory(self.owner, 2027)['value'], D('180000.00'))
        self.assertEqual(R.purchase_report(self.owner, 2026)['totals']['gross'], D('800000.00'))
        self.assertEqual(R.purchase_report(self.owner, 2026)['returns']['quantity'], 10)
        self.assertTrue(R.inventory_rollforward(self.owner, 2026, today=date(2027, 6, 30))['balanced'])

    def test_untracked_manual_stock_edit_reported_not_invented(self):
        Product.objects.filter(pk=self.d.pk).update(quantity=self.d.quantity + 7)     # Update Product page edit
        roll = R.inventory_rollforward(self.owner, 2027, today=date(2027, 10, 1))
        self.assertTrue(roll['is_current_year'])
        self.assertEqual(roll['untracked_quantity'], 7)
        self.assertEqual(roll['untracked_value'], D('14000.00'))
        self.assertEqual(R.opening_inventory(self.owner, 2027)['value'], D('200000.00'))   # history unchanged

    def test_no_data_changes_and_repeatable(self):     # Test H + I
        before = snapshot()
        first = [R.opening_inventory(self.owner, 2027)['value'], R.fy_summary(self.owner, 2027)['purchase']['gross'],
                 R.inventory_rollforward(self.owner, 2026, today=date(2027, 6, 30))['closing']['value']]
        for _ in range(3):
            again = [R.opening_inventory(self.owner, 2027)['value'], R.fy_summary(self.owner, 2027)['purchase']['gross'],
                     R.inventory_rollforward(self.owner, 2026, today=date(2027, 6, 30))['closing']['value']]
            self.assertEqual(again, first)
        self.assertEqual(snapshot(), before)             # no rows added, changed or removed anywhere
        self.assertEqual(Product.objects.count(), 4)     # same inventory, no per-year copies

    def test_previous_year_invoices_still_accessible(self):
        self.client.force_login(self.owner)
        old = Order.objects.filter(financial_year=2025).first()
        self.assertEqual(self.client.get(f'/store/{self.owner.username}/invoice/{old.id}/').status_code, 200)
        self.assertEqual(list(Order.objects.order_by('id').values_list('financial_year', 'order_number')),
                         [(2025, 1), (2026, 1), (2026, 2), (2026, 3), (2027, 1)])

    def test_compare_page_shows_rollforward(self):
        self.client.force_login(self.owner)
        with mock.patch('store.fy_reports.timezone.localdate', return_value=date(2027, 10, 1)):
            resp = self.client.get(reverse('fy_analytics', args=['compare']), {'fy': '2026'})
        roll = resp.context['rollforward']
        self.assertEqual((roll['opening']['value'], roll['closing']['value']), (D('50000.00'), D('200000.00')))
        self.assertContains(resp, 'Closing stock on 31 March 2027')
        self.assertContains(resp, 'opening stock of FY 2027-28')


class MissingCostTests(TestCase):
    def test_lot_without_cost_is_flagged_not_priced_at_selling_price(self):
        owner = make_owner()
        p = Product.objects.create(store_owner=owner, purchased_from='Old', purchase_date=date(2026, 5, 1),
                                   purchase_invoice_number='OLD-1', name='Legacy Urea', price=D('350'), quantity=20)
        rep = R.purchase_report(owner, 2026)
        self.assertEqual(rep['missing_cost'], ['Legacy Urea'])
        self.assertEqual(rep['totals']['gross'], D('0.00'))                 # not 20 x 350
        self.assertEqual(R.opening_inventory(owner, 2027)['missing_cost'], ['Legacy Urea'])
        self.assertEqual(R.opening_inventory(owner, 2027)['value'], D('0.00'))
        self.client.force_login(owner)
        with mock.patch('store.fy_reports.timezone.localdate', return_value=date(2026, 10, 6)):
            resp = self.client.get(reverse('fy_analytics', args=['purchases']), {'fy': '2026'})
        self.assertContains(resp, 'no purchase cost saved')
