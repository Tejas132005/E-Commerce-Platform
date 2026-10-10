"""
Item-wise profit (store.fy_reports.profit_report), the home profit boxes, the profit page,
and the Sales − Purchase difference rule. Separate test database; rolled back after each test.
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from store import fy_reports as R
from store.models import Order, Product
from .helpers import make_customer, make_owner
from .test_fy_reports import lot, sell, snapshot

D = Decimal


def item(report, name):
    return next(r for r in report['items'] if r['name'] == name)


# ---------------------------------------------------------------- Test A

class DifferenceRuleTests(TestCase):
    """Difference = Sales − Purchase."""

    def test_sales_less_than_purchases_negative_red(self):
        d = R.difference_display(purchase=D('500000'), sales=D('300000'))
        self.assertEqual((d['value'], d['text'], d['tone']), (D('-200000.00'), '\u2212₹2,00,000.00', 'purchase-higher'))

    def test_sales_greater_than_purchases_positive_green(self):
        d = R.difference_display(purchase=D('300000'), sales=D('500000'))
        self.assertEqual((d['value'], d['text'], d['tone']), (D('200000.00'), '+₹2,00,000.00', 'sales-higher'))

    def test_equal_zero_neutral(self):
        d = R.difference_display(purchase=D('500000'), sales=D('500000'))
        self.assertEqual((d['value'], d['text'], d['tone']), (D('0.00'), '₹0.00', 'neutral'))

    def test_page_colours(self):
        # tone classes map to colours in the templates: purchase-higher = red, sales-higher = green
        with open(settings.BASE_DIR / 'templates' / 'home.html', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.tone-purchase-higher { color: var(--danger)', css)
        self.assertIn('.tone-sales-higher { color: var(--amount)', css)
        self.assertIn('Sales − Purchase', css)


# ---------------------------------------------------------------- Tests B, C, E

class BasicProfitTests(TestCase):
    """Purchase 10 units at ₹80; sell at ₹100 (excl. GST), GST 5%."""

    def setUp(self):
        self.owner = make_owner()
        self.c = make_customer(self.owner)
        self.p = lot(self.owner, 'Urea', 10, '80', date(2026, 4, 2), gst='5')

    def test_b_and_c_profit_excl_and_incl_gst(self):
        sell(self.owner, self.c, self.p, 10, '100', date(2026, 5, 1), gst='5')   # 1,000 + 50 GST
        r = item(R.profit_report(self.owner, 2026), 'Urea')
        self.assertEqual((r['taxable'], r['gst'], r['gross'], r['cost']), (D('1000.00'), D('50.00'), D('1050.00'), D('800.00')))
        self.assertEqual(r['profit_ex'], D('200.00'))          # Test B
        self.assertEqual(r['profit_in'], D('250.00'))          # Test C
        self.assertEqual(r['profit_ex_display']['tone'], 'gain')

    def test_e_partial_quantity_costs_only_units_sold(self):
        sell(self.owner, self.c, self.p, 4, '100', date(2026, 5, 1), gst='5')
        r = item(R.profit_report(self.owner, 2026), 'Urea')
        self.assertEqual(r['quantity'], 4)
        self.assertEqual(r['cost'], D('320.00'))               # 4 x 80, not 10 x 80 = 800
        self.assertEqual(r['profit_ex'], D('80.00'))           # 400 - 320

    def test_loss_is_negative_and_red(self):
        sell(self.owner, self.c, self.p, 5, '70', date(2026, 5, 1))
        rep = R.profit_report(self.owner, 2026)
        self.assertEqual(rep['profit_ex']['value'], D('-50.00'))
        self.assertEqual((rep['profit_ex']['text'], rep['profit_ex']['tone']), ('\u2212₹50.00', 'loss'))
        self.assertEqual(rep['loss_items'], 1)

    def test_zero_profit_neutral(self):
        sell(self.owner, self.c, self.p, 1, '80', date(2026, 5, 1))
        self.assertEqual(R.profit_report(self.owner, 2026)['profit_ex']['tone'], 'neutral')


# ---------------------------------------------------------------- Tests D, F, G

class InvoiceRateAndCostingTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.c = make_customer(self.owner)

    def test_d_actual_invoice_rates_not_current_price(self):
        p = lot(self.owner, 'DAP', 20, '1000', date(2026, 4, 2), gst='5')
        sell(self.owner, self.c, p, 2, '1200', date(2026, 5, 1), gst='5')
        sell(self.owner, self.c, p, 3, '1350', date(2026, 6, 1), gst='5')
        Product.objects.filter(pk=p.pk).update(price=D('9999'))           # current selling price changed later
        r = item(R.profit_report(self.owner, 2026), 'DAP')
        self.assertEqual(r['taxable'], D('6450.00'))                        # 2x1200 + 3x1350
        self.assertEqual((r['min_rate'], r['max_rate'], r['avg_rate']), (D('1200.00'), D('1350.00'), D('1290.00')))
        self.assertEqual(r['profit_ex'], D('1450.00'))                      # 6450 - 5x1000

    def test_f_lots_bought_at_different_costs(self):
        # Specific identification: each sale is costed at the lot it came from.
        a = lot(self.owner, 'MOP', 10, '80', date(2026, 4, 2))
        b = lot(self.owner, 'MOP', 10, '100', date(2026, 7, 2))
        sell(self.owner, self.c, a, 5, '120', date(2026, 8, 1))
        sell(self.owner, self.c, b, 3, '120', date(2026, 9, 1))
        rep = R.profit_report(self.owner, 2026)
        self.assertEqual(len(rep['items']), 1)                              # one item row for both lots
        r = item(rep, 'MOP')
        self.assertEqual((r['lots'], r['quantity'], r['cost']), (2, 8, D('700.00')))   # 5x80 + 3x100
        self.assertEqual(r['profit_ex'], D('260.00'))                       # 960 - 700
        # not latest cost (8x100 = 800) and not average cost (8x90 = 720)
        self.assertNotIn(r['cost'], (D('800.00'), D('720.00')))

    def test_g_multiple_invoices_aggregate(self):
        p = lot(self.owner, 'NPK', 50, '1000', date(2026, 4, 2), gst='5')
        for qty, rate, day in [(2, '1100', date(2026, 5, 1)), (5, '1150', date(2026, 6, 1)), (1, '1300', date(2026, 7, 1))]:
            sell(self.owner, self.c, p, qty, rate, day, gst='5')
        r = item(R.profit_report(self.owner, 2026), 'NPK')
        self.assertEqual(r['quantity'], 8)
        self.assertEqual(r['taxable'], D('9250.00'))                        # 2200 + 5750 + 1300
        self.assertEqual(r['gross'], D('9712.50'))
        self.assertEqual((r['profit_ex'], r['profit_in']), (D('1250.00'), D('1712.50')))

    def test_deleted_invoices_and_other_stores_excluded(self):
        p = lot(self.owner, 'Zinc', 10, '50', date(2026, 4, 2))
        o = sell(self.owner, self.c, p, 2, '90', date(2026, 5, 1))
        sell(self.owner, self.c, p, 1, '90', date(2026, 5, 2))
        Order.objects.filter(pk=o.pk).update(is_deleted=True, order_number=1000000 + o.pk)
        other = make_owner(phone='9000000002', username='shop2')
        sell(other, make_customer(other, phone='8000000002'), lot(other, 'Zinc', 10, '1', date(2026, 4, 2)), 5, '500', date(2026, 5, 1))
        r = item(R.profit_report(self.owner, 2026), 'Zinc')
        self.assertEqual((r['quantity'], r['profit_ex']), (1, D('40.00')))

    def test_missing_cost_flagged(self):
        p = Product.objects.create(store_owner=self.owner, purchased_from='Old', purchase_date=date(2026, 4, 2),
                                   purchase_invoice_number='X', name='Legacy', price=D('0'), quantity=5)
        sell(self.owner, self.c, p, 1, '100', date(2026, 5, 1))
        self.assertEqual(R.profit_report(self.owner, 2026)['missing_cost'], ['Legacy'])


# ---------------------------------------------------------------- Test H

class FinancialYearProfitTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        c = make_customer(self.owner)
        self.old = lot(self.owner, 'Urea', 100, '200', date(2026, 2, 1))     # bought in FY 2025-26
        sell(self.owner, c, self.old, 30, '250', date(2026, 3, 20))           # FY 2025-26 sale
        sell(self.owner, c, self.old, 20, '260', date(2026, 4, 5))            # FY 2026-27 sale from opening stock
        self.new = lot(self.owner, 'Urea', 50, '220', date(2026, 6, 1))       # FY 2026-27 purchase
        sell(self.owner, c, self.new, 10, '270', date(2026, 8, 1))
        sell(self.owner, c, self.new, 5, '275', date(2027, 4, 2))             # FY 2027-28 - excluded

    def test_only_current_year_sales_counted(self):
        r = item(R.profit_report(self.owner, 2026), 'Urea')
        self.assertEqual(r['quantity'], 30)                                  # 20 + 10
        self.assertEqual(r['taxable'], D('7900.00'))                         # 20x260 + 10x270
        self.assertEqual(r['cost'], D('6200.00'))                            # 20x200 + 10x220
        self.assertEqual(r['profit_ex'], D('1700.00'))

    def test_opening_stock_cost_used_for_units_sold_from_it(self):
        rep = R.profit_report(self.owner, 2026)
        self.assertEqual(rep['totals']['cost_from_opening_stock'], D('4000.00'))   # 20 x 200 from the FY 2025-26 lot
        self.assertEqual(R.opening_inventory(self.owner, 2026)['value'], D('14000.00'))   # 70 x 200 carried in
        # opening stock is not a purchase of the new year
        self.assertEqual(R.purchase_report(self.owner, 2026)['totals']['gross'], D('11000.00'))   # only the 50 x 220 lot

    def test_previous_year_profit_separate(self):
        r = item(R.profit_report(self.owner, 2025), 'Urea')
        self.assertEqual((r['quantity'], r['profit_ex']), (30, D('1500.00')))      # 30 x (250 - 200)
        self.assertEqual(item(R.profit_report(self.owner, 2027), 'Urea')['quantity'], 5)

    def test_cost_never_counted_twice_across_years(self):
        sold_cost = sum(R.profit_report(self.owner, fy)['totals']['cost'] for fy in (2025, 2026, 2027))
        self.assertEqual(sold_cost, D('30') * 200 + D('20') * 200 + D('15') * 220)


# ---------------------------------------------------------------- Test I + J

@mock.patch('store.fy_reports.timezone.localdate', return_value=date(2026, 10, 6))
class ConsistencyAndPagesTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        c = make_customer(self.owner)
        a = lot(self.owner, 'Urea', 100, '250', date(2026, 4, 2), category='Nitrogen', gst='5')
        b = lot(self.owner, 'DAP', 40, '1300', date(2026, 4, 3), category='Phosphate', gst='5')
        z = lot(self.owner, 'Zinc', 20, '400', date(2026, 4, 4), category='Micro', gst='5')
        sell(self.owner, c, a, 10, '300', date(2026, 5, 1), gst='5')
        sell(self.owner, c, b, 4, '1450', date(2026, 6, 1), gst='5')
        sell(self.owner, c, z, 5, '350', date(2026, 7, 1), gst='5')         # sold at a loss
        old = lot(self.owner, 'Old', 10, '100', date(2025, 5, 1))
        sell(self.owner, c, old, 2, '150', date(2025, 6, 1))                 # FY 2025-26
        self.client.force_login(self.owner)

    def test_graph_matches_table_and_boxes(self, _):
        resp = self.client.get(reverse('fy_analytics', args=['profit']), {'fy': '2026'})
        self.assertEqual(resp.status_code, 200)
        chart, items = resp.context['chart'], resp.context['profit']['items']
        self.assertEqual(chart['names'], [r['name'] for r in items])
        self.assertEqual(chart['profit_ex'], [float(r['profit_ex']) for r in items])
        self.assertEqual(chart['profit_in'], [float(r['profit_in']) for r in items])
        self.assertEqual(chart['names'], ['DAP', 'Urea', 'Zinc'])            # 600, 500, -250: highest first, loss last
        self.assertLess(chart['profit_ex'][-1], 0)
        total_ex = sum(r['profit_ex'] for r in items)
        summary = R.fy_summary(self.owner, 2026)
        self.assertEqual(summary['profit_ex']['value'], total_ex)
        self.assertEqual(summary['profit_ex']['value'], D('850.00'))         # 500 + 600 - 250
        self.assertEqual(summary['profit_in']['value'], sum(r['profit_in'] for r in items))
        self.assertContains(resp, 'id="profitChart"')
        self.assertContains(resp, 'Profit incl. GST')

    def test_home_boxes_link_and_follow_fy(self, _):
        with mock.patch('core.dashboard.timezone.localdate', return_value=date(2026, 10, 6)):
            html = self.client.get('/', {'range': 'fy'}).content.decode()
            self.assertIn('tone-gain">+₹850.00', html)
            self.assertIn(reverse('fy_analytics', args=['profit']) + '?fy=2026', html)
            cur = self.client.get('/core/home-stats/', {'range': 'fy'}).json()['fy_summary']
            past = self.client.get('/core/home-stats/', {'range': 'fy2025'}).json()['fy_summary']
        self.assertEqual(cur['profit_ex']['text'], '+₹850.00')
        self.assertEqual(past['profit_ex']['text'], '+₹100.00')            # 2 x (150 - 100)
        self.assertEqual(self.client.get(reverse('fy_analytics', args=['profit']), {'fy': '2025'}).context['chart']['names'], ['Old'])

    def test_j_profit_analytics_change_no_data(self, _):
        before = snapshot()
        for _ in range(2):
            R.profit_report(self.owner, 2026)
            self.client.get(reverse('fy_analytics', args=['profit']), {'fy': '2026'})
            self.client.get('/core/home-stats/', {'range': 'fy'})
        self.assertEqual(snapshot(), before)
