import os
import sys
import django
from datetime import timedelta, date

sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'E-Commerce.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from accounts.models import CustomUser
from store.models import Product, ShopCustomer, Cart, Order, OrderItem, SalesReport
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from store.views import add_to_cart_view, checkout_view, delete_invoice, restore_invoice

def test_flow():
    print("--- STARTING CHECKOUT, STOCK, AND DATE TESTS ---")
    
    # 1. Get or create test store owner and customer
    user = CustomUser.objects.first()
    if not user:
        user = CustomUser.objects.create(username='test_owner', email='owner@test.com', dob='1990-01-01')
    customer, _ = ShopCustomer.objects.get_or_create(
        store_owner=user, phone='1234567890', defaults={'name': 'Test Customer'}
    )

    # Clean up previous test data
    Cart.objects.filter(store_owner=user, customer=customer).delete()
    Order.objects.filter(store_owner=user, customer=customer).delete()
    Product.objects.filter(store_owner=user, name='Test Fertilizer Product').delete()

    # 2. Create a test product with stock = 5
    product = Product.objects.create(
        store_owner=user,
        purchased_from='Test Supplier',
        purchase_date=timezone.now().date(),
        purchase_invoice_number='PINV-001',
        name='Test Fertilizer Product',
        price=Decimal('100.00'),
        quantity=5,
        gst=Decimal('18.00'),
        unit_capacity=Decimal('10.00'),
        taxable_unit_amount=Decimal('100.00'),
    )
    print(f"Created product with stock: {product.quantity}")

    factory = RequestFactory()

    # TEST FUTURE DATE: Try adding item with tomorrow's date (Should fail)
    tomorrow = timezone.now().date() + timedelta(days=1)
    req_future = factory.post(f'/store/{user.username}/cart/add/{product.id}/', {
        'quantity': '1',
        'amount': '100.00',
        'transaction_date': str(tomorrow)
    })
    req_future.session = {f'customer_id_{user.username}': customer.phone}
    messages_storage = FallbackStorage(req_future)
    setattr(req_future, '_messages', messages_storage)
    
    add_to_cart_view(req_future, user.username, product.id)
    cart_item_future = Cart.objects.filter(store_owner=user, customer=customer, product=product).first()
    assert cart_item_future is None, "Cart item should NOT be created for a future date"
    error_msgs = [str(m) for m in messages_storage]
    assert any("Future dates are not allowed" in m for m in error_msgs), f"Expected future date error message, got {error_msgs}"
    print("OK: FUTURE DATE TEST PASSED: Blocked addition with future date.")

    # TEST A: Add quantity 3 with today's date (Should succeed)
    req = factory.post(f'/store/{user.username}/cart/add/{product.id}/', {
        'quantity': '3',
        'amount': '100.00',
        'transaction_date': str(timezone.now().date())
    })
    req.session = {f'customer_id_{user.username}': customer.phone}
    setattr(req, '_messages', FallbackStorage(req))
    
    add_to_cart_view(req, user.username, product.id)
    cart_item = Cart.objects.filter(store_owner=user, customer=customer, product=product).first()
    assert cart_item is not None and cart_item.quantity == 3, f"Expected cart item qty 3, got {cart_item.quantity if cart_item else None}"
    print("OK: TEST A PASSED: Added 3 units to cart successfully.")

    # TEST B: Try adding 3 more (3 + 3 = 6 > stock of 5, should fail)
    req2 = factory.post(f'/store/{user.username}/cart/add/{product.id}/', {
        'quantity': '3',
        'amount': '100.00',
        'transaction_date': str(timezone.now().date())
    })
    req2.session = {f'customer_id_{user.username}': customer.phone}
    setattr(req2, '_messages', FallbackStorage(req2))
    
    add_to_cart_view(req2, user.username, product.id)
    cart_item = Cart.objects.filter(store_owner=user, customer=customer, product=product).first()
    assert cart_item.quantity == 3, f"Expected cart item qty to remain 3 after failed add, got {cart_item.quantity}"
    print("OK: TEST B PASSED: Excess addition prevented (cart quantity remained 3).")

    # TEST C: Manually set cart quantity to 10 (simulating stock reduction after cart addition), then test checkout
    cart_item.quantity = 10
    cart_item.save()

    req_checkout = factory.get(f'/store/{user.username}/checkout/')
    req_checkout.session = {f'customer_id_{user.username}': customer.phone}
    setattr(req_checkout, '_messages', FallbackStorage(req_checkout))

    res_checkout = checkout_view(req_checkout, user.username)
    
    # Verify checkout failed and redirected to cart_view
    assert res_checkout.status_code == 302 and 'cart' in res_checkout.url, f"Expected redirect to cart_view, got {res_checkout.url}"
    # Verify product stock unchanged (still 5)
    product.refresh_from_db()
    assert product.quantity == 5, f"Expected product stock 5, got {product.quantity}"
    # Verify cart not cleared
    cart_item.refresh_from_db()
    assert cart_item.quantity == 10, "Cart item should not be cleared on failed checkout"
    # Verify no order created
    assert Order.objects.filter(store_owner=user, customer=customer).count() == 0, "No order should be created"
    print("OK: TEST C PASSED: Checkout with insufficient stock aborted gracefully without negative stock or partial order.")

    # TEST D: Fix cart quantity to 2 with past date (2026-09-01) and checkout
    past_date = date(2026, 9, 1)
    cart_item.quantity = 2
    cart_item.transaction_date = past_date
    cart_item.save()

    req_checkout_success = factory.get(f'/store/{user.username}/checkout/')
    req_checkout_success.session = {f'customer_id_{user.username}': customer.phone}
    setattr(req_checkout_success, '_messages', FallbackStorage(req_checkout_success))

    res_checkout_success = checkout_view(req_checkout_success, user.username)
    assert res_checkout_success.status_code == 302 and 'orders' in res_checkout_success.url, f"Expected redirect to my_orders, got {res_checkout_success.url}"

    # Verify stock reduced from 5 to 3
    product.refresh_from_db()
    assert product.quantity == 3, f"Expected product stock 3 after checkout, got {product.quantity}"

    # Verify cart is empty
    assert Cart.objects.filter(store_owner=user, customer=customer).count() == 0, "Cart should be empty after successful checkout"

    # Verify order created and invoice_date matches cart transaction date
    order = Order.objects.filter(store_owner=user, customer=customer).first()
    assert order is not None, "Order should be created"
    assert order.invoice_date == past_date, f"Expected invoice_date {past_date}, got {order.invoice_date}"

    # Verify SalesReport sale_date matches cart transaction date
    sales_report = SalesReport.objects.filter(order=order).first()
    assert sales_report is not None and sales_report.sale_date.date() == past_date, f"Expected SalesReport date {past_date}, got {sales_report.sale_date.date() if sales_report else None}"
    print("OK: TEST D PASSED: Successful checkout saved correct cart invoice_date and SalesReport date.")

    # TEST E: Delete invoice and check stock restoration
    req_delete = factory.post(f'/store/{user.username}/invoice/{order.id}/delete/')
    req_delete.session = {f'customer_id_{user.username}': customer.phone}
    setattr(req_delete, '_messages', FallbackStorage(req_delete))

    delete_invoice(req_delete, user.username, order.id)
    product.refresh_from_db()
    assert product.quantity == 5, f"Expected product stock restored to 5 after invoice deletion, got {product.quantity}"
    print("OK: TEST E PASSED: Deleting invoice restored product stock from 3 to 5.")

    # TEST F: Restore invoice and check stock deduction
    req_restore = factory.post(f'/store/{user.username}/invoice/{order.id}/restore/')
    req_restore.session = {f'customer_id_{user.username}': customer.phone}
    setattr(req_restore, '_messages', FallbackStorage(req_restore))

    restore_invoice(req_restore, user.username, order.id)
    product.refresh_from_db()
    assert product.quantity == 3, f"Expected product stock reduced back to 3 after invoice restore, got {product.quantity}"
    print("OK: TEST F PASSED: Restoring invoice deducted product stock from 5 to 3.")

    # Clean up test data
    Order.objects.filter(store_owner=user, customer=customer).delete()
    Product.objects.filter(store_owner=user, name='Test Fertilizer Product').delete()
    print("--- ALL TESTS PASSED SUCCESSFULLY! ---")

if __name__ == '__main__':
    test_flow()
