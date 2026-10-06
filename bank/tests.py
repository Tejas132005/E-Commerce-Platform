"""
Bank Payment Management tests.

Run on Django's separate test database; every test is rolled back.

Transfer design under test:
  Credited -> +amount, Debited -> -amount,
  Transferred OUT (to another account) -> -amount, Transferred IN (from another account) -> +amount.
  A transfer is counted once, never as both income and expense, and is reported
  separately from Credited/Debited.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from bank.forms import BankTransactionForm
from bank.models import BankTransaction
from store.models import Order, OrderItem, Product, SalesReport, ShopCustomer
from store.tests.helpers import make_customer, make_invoice, make_owner, make_product

URL = 'bank_payment_management'


class BankTransactionTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.client.force_login(self.owner)

    def add(self, amount, ttype, description='x', direction='', counterparty='', day='2026-10-06'):
        return self.client.post(reverse(URL), {
            'transaction_date': day, 'transaction_type': ttype, 'amount': str(amount),
            'transfer_direction': direction, 'counterparty_account': counterparty,
            'description': description,
        })

    def balance(self):
        return BankTransaction.objects.filter(store_owner=self.owner).balance()

    def test_page_loads_with_three_type_dropdown(self):
        resp = self.client.get(reverse(URL))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Bank Payment Management')
        self.assertContains(resp, '<select name="transaction_type"', html=False)
        values = [v for v, _ in resp.context['form'].fields['transaction_type'].choices if v]
        self.assertEqual(values, ['credited', 'debited', 'transferred'])
        self.assertEqual(resp.context['summary']['balance'], Decimal('0.00'))

    # Test 7
    def test_credit_increases_balance(self):
        resp = self.add(10000, 'credited', 'Test credit')
        self.assertRedirects(resp, reverse(URL))
        self.assertEqual(self.balance(), Decimal('10000.00'))

    # Test 8
    def test_debit_decreases_balance(self):
        self.add(10000, 'credited', 'Test credit')
        self.add(3000, 'debited', 'Test debit')
        self.assertEqual(self.balance(), Decimal('7000.00'))

    def test_debit_alone_goes_negative(self):
        self.add(3000, 'debited', 'Test debit')
        self.assertEqual(self.balance(), Decimal('-3000.00'))

    # Test 9
    def test_transfer_out_and_in(self):
        self.add(10000, 'credited', 'Opening')
        self.add(2500, 'transferred', 'Moved to savings', direction='out', counterparty='SBI Savings ****1234')
        txn = BankTransaction.objects.get(transaction_type='transferred')
        self.assertEqual((txn.amount, txn.transfer_direction, txn.counterparty_account),
                         (Decimal('2500.00'), 'out', 'SBI Savings ****1234'))
        self.assertEqual(self.balance(), Decimal('7500.00'))           # counted once, as outflow
        self.add(1000, 'transferred', 'Back from savings', direction='in')
        self.assertEqual(self.balance(), Decimal('8500.00'))
        summary = BankTransaction.objects.filter(store_owner=self.owner).summary()
        # transfers are NOT reported as income/expense
        self.assertEqual(summary['credited'], Decimal('10000.00'))
        self.assertEqual(summary['debited'], Decimal('0.00'))
        self.assertEqual((summary['transferred_out'], summary['transferred_in']), (Decimal('2500.00'), Decimal('1000.00')))
        self.assertEqual(summary['balance'], self.balance())

    def test_transfer_requires_direction(self):
        resp = self.add(500, 'transferred', 'No direction')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('transfer_direction', resp.context['form'].errors)
        self.assertFalse(BankTransaction.objects.exists())

    def test_direction_ignored_for_non_transfers(self):
        self.add(500, 'credited', 'Credit', direction='out', counterparty='Junk')
        txn = BankTransaction.objects.get()
        self.assertEqual((txn.transfer_direction, txn.counterparty_account), ('', ''))
        self.assertEqual(self.balance(), Decimal('500.00'))

    # Test 10
    def test_multiple_transactions_and_running_balance(self):
        self.add(10000, 'credited', 'c1', day='2026-10-01')
        self.add(3000, 'debited', 'd1', day='2026-10-02')
        self.add(2000, 'transferred', 't1', direction='out', day='2026-10-03')
        self.add(500.50, 'credited', 'c2', day='2026-10-04')
        self.add(1200.25, 'debited', 'd2', day='2026-10-05')
        expected = Decimal('10000') - 3000 - 2000 + Decimal('500.50') - Decimal('1200.25')
        self.assertEqual(self.balance(), expected)  # 4300.25
        resp = self.client.get(reverse(URL))
        self.assertEqual(resp.context['summary']['balance'], expected)
        running = [r['running_balance'] for r in resp.context['rows']]   # newest first
        self.assertEqual(running, [Decimal('4300.25'), Decimal('5500.50'), Decimal('5000.00'),
                                   Decimal('7000.00'), Decimal('10000.00')])
        self.assertContains(resp, '₹4300.25')

    # Test 11
    def test_description_stored_and_shown(self):
        text = 'Fertilizer supplier payment\nIFFCO invoice 778'
        self.add(4200, 'debited', text)
        self.assertEqual(BankTransaction.objects.get().description, text)
        self.assertContains(self.client.get(reverse(URL)), 'IFFCO invoice 778')

    def test_validation_amount_and_description(self):
        for amount, desc in [(0, 'zero'), (-5, 'negative'), ('abc', 'text'), (100, '   ')]:
            resp = self.add(amount, 'credited', desc)
            self.assertEqual(resp.status_code, 200)
        self.assertFalse(BankTransaction.objects.exists())
        resp = self.add(100, 'bogus', 'bad type')
        self.assertIn('transaction_type', resp.context['form'].errors)

    def test_model_clean_rejects_transfer_without_direction(self):
        txn = BankTransaction(store_owner=self.owner, transaction_type='transferred',
                              amount=Decimal('1'), description='x')
        with self.assertRaises(ValidationError):
            txn.full_clean()

    def test_form_defaults_date_to_today(self):
        self.assertIsNotNone(BankTransactionForm().initial['transaction_date'])

    def test_delete_recalculates_balance(self):
        self.add(1000, 'credited', 'c')
        self.add(400, 'debited', 'd')
        debit = BankTransaction.objects.get(transaction_type='debited')
        self.client.post(reverse('delete_bank_transaction', args=[debit.pk]))
        self.assertEqual(self.balance(), Decimal('1000.00'))

    def test_delete_requires_post(self):
        self.add(1000, 'credited', 'c')
        resp = self.client.get(reverse('delete_bank_transaction', args=[BankTransaction.objects.get().pk]))
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(BankTransaction.objects.count(), 1)


class BankSecurityTests(TestCase):
    def setUp(self):
        self.owner = make_owner()
        self.other = make_owner(phone='9000000002', username='shop2')

    def test_login_required(self):
        resp = self.client.get(reverse(URL))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        resp = client.post(reverse(URL), {'transaction_type': 'credited', 'amount': '1',
                                          'description': 'x', 'transaction_date': '2026-10-06'})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(BankTransaction.objects.exists())

    def test_owners_see_only_their_own_transactions(self):
        BankTransaction.objects.create(store_owner=self.other, transaction_type='credited',
                                       amount=Decimal('999'), description='other shop')
        self.client.force_login(self.owner)
        resp = self.client.get(reverse(URL))
        self.assertEqual(resp.context['rows'], [])
        self.assertEqual(resp.context['summary']['balance'], Decimal('0.00'))
        self.assertNotContains(resp, 'other shop')

    def test_cannot_delete_another_owners_transaction(self):
        txn = BankTransaction.objects.create(store_owner=self.other, transaction_type='credited',
                                             amount=Decimal('999'), description='other shop')
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('delete_bank_transaction', args=[txn.pk]))
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(BankTransaction.objects.filter(pk=txn.pk).exists())


class BankIsolationFromBillingTests(TestCase):
    """Test 12: bank transactions never touch products, customers, invoices, sales or numbering."""

    def snapshot(self):
        return {
            'products': list(Product.objects.order_by('pk').values()),
            'customers': list(ShopCustomer.objects.order_by('pk').values()),
            'orders': list(Order.objects.order_by('pk').values()),
            'items': list(OrderItem.objects.order_by('pk').values()),
            'sales': list(SalesReport.objects.order_by('pk').values()),
            'next_invoice': Order.next_invoice_sequence(self.owner, 2026),
        }

    def setUp(self):
        self.owner = make_owner()
        self.customer = make_customer(self.owner)
        self.product = make_product(self.owner, quantity=75)
        for _ in range(2):
            make_invoice(self.owner, self.customer, date(2026, 5, 1))
        self.client.force_login(self.owner)

    def test_bank_activity_leaves_billing_untouched(self):
        before = self.snapshot()
        self.assertEqual(before['next_invoice'], 3)
        for ttype, direction in [('credited', ''), ('debited', ''), ('transferred', 'out'), ('transferred', 'in')]:
            self.client.post(reverse(URL), {'transaction_date': '2026-05-02', 'transaction_type': ttype,
                                            'amount': '1500', 'transfer_direction': direction,
                                            'description': 'Customer refund'})
        BankTransaction.objects.first().delete()
        self.assertEqual(BankTransaction.objects.count(), 3)
        self.assertEqual(self.snapshot(), before)
        # Next real invoice still continues the billing sequence
        self.assertEqual(make_invoice(self.owner, self.customer, date(2026, 5, 3)).order_number, 3)

    def test_model_has_no_link_to_billing_tables(self):
        related = {f.related_model._meta.label for f in BankTransaction._meta.get_fields() if f.is_relation}
        self.assertEqual(related, {'accounts.CustomUser'})
