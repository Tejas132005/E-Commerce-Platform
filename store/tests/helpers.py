"""Shared fixtures for store tests. Everything here runs inside Django's test DB."""
from datetime import date
from decimal import Decimal

from accounts.models import CustomUser
from store.models import Cart, Order, Product, ShopCustomer


def make_owner(phone='9000000001', username='shop1'):
    return CustomUser.objects.create_user(
        phone=phone, email=f'{username}@example.com', username=username,
        password='pass12345', dob=date(1990, 1, 1), location='Bengaluru',
    )


def make_product(owner, name='Urea 45kg', quantity=100, price='300.00', gst='5.00'):
    return Product.objects.create(
        store_owner=owner, purchased_from='IFFCO', purchase_date=date(2025, 4, 1),
        purchase_invoice_number='PUR-1', name=name, price=Decimal(price),
        quantity=quantity, gst=Decimal(gst), taxable_unit_amount=Decimal(price),
    )


def make_customer(owner, phone='8000000001', name='Ramesh'):
    return ShopCustomer.objects.create(store_owner=owner, phone=phone, name=name)


def make_invoice(owner, customer, invoice_date):
    """Create an invoice the same way checkout does (number assigned by Order.save)."""
    order = Order.objects.create(
        store_owner=owner, customer=customer, total_price=Decimal('315.00'),
        subtotal=Decimal('300.00'), total_cgst=Decimal('7.50'), total_sgst=Decimal('7.50'),
        total_gst=Decimal('15.00'), invoice_date=invoice_date,
    )
    order.invoice_number = f"INV-{order.order_number:02d}"
    order.save()
    return order


def login_customer(client, owner, customer):
    session = client.session
    session[f'customer_id_{owner.username}'] = customer.phone
    session.save()


def add_cart_line(owner, customer, product, quantity, transaction_date):
    return Cart.objects.create(
        store_owner=owner, customer=customer, product=product, quantity=quantity,
        unit_price=product.price, total_price=product.price * quantity,
        transaction_date=transaction_date,
    )
