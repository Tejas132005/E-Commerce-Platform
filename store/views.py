# store/views.py 

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
from .models import Product, Cart, Order, OrderItem, SalesReport, ShopCustomer
from .forms import AddProductForm, UpdateProductForm, CustomerLoginForm, CustomerRegisterForm
from accounts.models import CustomUser
from collections import defaultdict
from decimal import Decimal
import html as html_stdlib
import re

from django.db.models import Q, Case, When, IntegerField, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta, time, date
import calendar

from .excel_export import build_workbook_response

# -------------------- HELPER FUNCTIONS --------------------


def _stock_export_product_leading_cells(product):
    """Leading CSV/XLSX columns: identity."""
    return [
        product.name,
        product.category or '',
        str(product.gst),
        product.hsn_code or '',
        product.batch_number or '',
        product.quantity,
        product.get_measurement_type_display(),
    ]


def _redirect_after_cart_error(request, username):
    next_path = (request.POST.get('next') or '').strip()
    if next_path.startswith('/') and not next_path.startswith('//'):
        return redirect(next_path)
    return redirect('store_products', username=username)


def _stock_detail_for_product(user, product, year, month):
    """
    Aggregate sold qty, sales amount, and tax breakdown for one product.
    month=None means entire year.
    Uses actual sales data from SalesReport (completed orders).
    """
    sold_quantity = 0
    total_amount_with_tax = Decimal('0.00')

    sales_qs = SalesReport.objects.filter(
        store_owner=user,
        product=product,
        sale_date__year=year,
    )
    if month is not None:
        sales_qs = sales_qs.filter(sale_date__month=month)

    sold_quantity = sales_qs.aggregate(total=Sum('quantity'))['total'] or 0
    total_amount_with_tax = sales_qs.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')

    # Determine tax type: IGST takes priority
    uses_igst = product.igst is not None and product.igst > 0

    igst_amount = Decimal('0.00')
    cgst_amount = Decimal('0.00')
    sgst_amount = Decimal('0.00')
    gst_amount = Decimal('0.00')
    sales_amount_ex_tax = Decimal('0.00')

    if uses_igst:
        igst_rate = Decimal(str(product.igst)) / Decimal('100')
        divisor = Decimal('1') + igst_rate
        if divisor > 0:
            sales_amount_ex_tax = total_amount_with_tax / divisor
            igst_amount = total_amount_with_tax - sales_amount_ex_tax
        # CGST/SGST/GST all zero for IGST products
    else:
        gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
        divisor = Decimal('1') + gst_rate_decimal
        if divisor > 0:
            sales_amount_ex_tax = total_amount_with_tax / divisor
            gst_amount = total_amount_with_tax - sales_amount_ex_tax
            cgst_amount = gst_amount / Decimal('2')
            sgst_amount = gst_amount / Decimal('2')

    current_stock = product.quantity
    initial_stock_for_period = int(current_stock) + int(sold_quantity)
    units_sold_period = int(initial_stock_for_period) - int(current_stock)

    # Stock values from Add Product data
    taxable_stock_value = product.taxable_unit_amount * current_stock
    total_stock_value = product.total_unit_amount * current_stock

    if current_stock == 0:
        stock_status = 'Out of Stock'
        status_class = 'danger'
    else:
        stock_status = 'In Stock'
        status_class = 'success'

    return {
        'product': product,
        'current_stock': current_stock,
        'initial_stock': initial_stock_for_period,
        'sold_quantity': units_sold_period,
        'total_amount_with_gst': total_amount_with_tax,
        'sales_amount': sales_amount_ex_tax,
        'gst_amount': gst_amount,
        'igst_amount': igst_amount,
        'cgst_amount': cgst_amount,
        'sgst_amount': sgst_amount,
        'taxable_stock_value': taxable_stock_value,
        'total_stock_value': total_stock_value,
        'stock_status': stock_status,
        'status_class': status_class,
        'category': product.category or 'Uncategorized',
        'batch_number': product.batch_number or '-',
    }

def get_store_owner(username):
    """Get store owner by username"""
    return get_object_or_404(CustomUser, username=username)

def get_logged_in_customer(request, store_owner):
    """Get logged in customer for a specific store"""
    customer_phone = request.session.get(f'customer_id_{store_owner.username}')
    if not customer_phone:
        return None
    try:
        return ShopCustomer.objects.get(phone=customer_phone, store_owner=store_owner)
    except ShopCustomer.DoesNotExist:
        return None

# -------------------- CUSTOMER AUTH --------------------

def customer_login(request, username):
    store_owner = get_store_owner(username)
    
    if request.method == 'POST':
        form = CustomerLoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            try:
                customer = ShopCustomer.objects.get(phone=phone, store_owner=store_owner)
                request.session[f'customer_id_{store_owner.username}'] = customer.phone
                return redirect('store_products', username=username)
            except ShopCustomer.DoesNotExist:
                form.add_error('phone', 'Customer not found. Please register.')
    else:
        form = CustomerLoginForm()
    
    return render(request, 'customer_login.html', {
        'form': form, 
        'store_owner': store_owner
    })

def customer_register(request, username):
    store_owner = get_store_owner(username)
    
    if request.method == 'POST':
        form = CustomerRegisterForm(request.POST)
        if form.is_valid():
            # Check if customer already exists
            phone = form.cleaned_data['phone']
            if ShopCustomer.objects.filter(phone=phone, store_owner=store_owner).exists():
                form.add_error('phone', 'A customer with this phone number already exists.')
            else:
                customer = form.save(commit=False)
                customer.store_owner = store_owner
                customer.save()
                request.session[f'customer_id_{store_owner.username}'] = customer.phone
                return redirect('store_products', username=username)
    else:
        form = CustomerRegisterForm()
    
    return render(request, 'customer_register.html', {
        'form': form,
        'store_owner': store_owner
    })

def customer_logout(request, username):
    request.session.pop(f'customer_id_{username}', None)
    return redirect('customer_login', username=username)

# -------------------- PERSONALIZED STORE --------------------

def store_products_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    # Get active (non-archived) products only
    all_products = Product.objects.filter(
        store_owner=store_owner, 
        is_archived=False
    ).order_by('category', 'name')

    context = {
        'all_products': all_products,
        'store_owner': store_owner,
        'customer': customer,
    }

    return render(request, 'store_products.html', context)

def product_detail_view(request, username, product_id):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    product = get_object_or_404(
        Product, id=product_id, store_owner=store_owner, is_archived=False,
    )
    return render(request, 'product_detail.html', {
        'product': product,
        'store_owner': store_owner,
        'customer': customer,
    })

# -------------------- CART & BILLING WITH GST - FIXED --------------------

def add_to_cart_view(request, username, product_id):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    if request.method == 'POST':
        product = get_object_or_404(
            Product,
            id=product_id,
            store_owner=store_owner,
            is_archived=False,
        )
        quantity = int(request.POST.get('quantity', 1))
        custom_amount = request.POST.get('amount', '').strip()
        date_raw = (request.POST.get('transaction_date') or request.POST.get('date', '')).strip()

        if not date_raw:
            from django.contrib import messages as msg
            msg.error(request, 'Please select a date for this line.')
            return _redirect_after_cart_error(request, username)

        try:
            transaction_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
        except ValueError:
            from django.contrib import messages as msg
            msg.error(request, 'Invalid date. Use the date picker.')
            return _redirect_after_cart_error(request, username)

        if not custom_amount:
            from django.contrib import messages as msg
            msg.error(request, 'Please enter an amount (unit price).')
            return _redirect_after_cart_error(request, username)

        unit_price = Decimal(str(custom_amount))
        if unit_price <= 0:
            from django.contrib import messages as msg
            msg.error(request, 'Amount must be greater than zero.')
            return _redirect_after_cart_error(request, username)

        if product.quantity <= 0:
            from django.contrib import messages as msg
            msg.error(request, 'This product is out of stock.')
            return _redirect_after_cart_error(request, username)

        if quantity > product.quantity:
            from django.contrib import messages as msg
            msg.error(request, f'Only {product.quantity} items available in stock.')
            return _redirect_after_cart_error(request, username)
        
        # Calculate total price WITHOUT GST for cart storage
        total_price_without_gst = unit_price * quantity

        cart_item, created = Cart.objects.get_or_create(
            store_owner=store_owner,
            customer=customer,
            product=product,
            defaults={
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price_without_gst,
                'transaction_date': transaction_date,
            }
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.quantity:
                from django.contrib import messages as msg
                msg.error(
                    request,
                    f'Cannot add more. Only {product.quantity} items available, you already have {cart_item.quantity} in cart.',
                )
                return _redirect_after_cart_error(request, username)

            cart_item.quantity = new_quantity
            cart_item.unit_price = unit_price
            cart_item.total_price = unit_price * cart_item.quantity
            cart_item.transaction_date = transaction_date
            cart_item.save()

        return redirect('cart_view', username=username)

def cart_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    Cart.objects.filter(
        store_owner=store_owner,
        customer=customer,
        product__is_archived=True,
    ).delete()

    cart_items = Cart.objects.filter(store_owner=store_owner, customer=customer)
    
    # Calculate totals with GST/IGST - FIXED: Proper Decimal handling
    subtotal = Decimal('0.00')
    total_gst = Decimal('0.00')
    total_igst = Decimal('0.00')
    
    cart_items_with_gst = []
    
    for item in cart_items:
        effective_price = item.unit_price if item.unit_price > 0 else item.product.price
        item_subtotal = effective_price * item.quantity
        
        # Determine tax type: IGST takes priority
        product = item.product
        uses_igst = product.igst is not None and product.igst > 0
        
        if uses_igst:
            igst_rate = Decimal(str(product.igst)) / Decimal('100')
            item_igst = item_subtotal * igst_rate
            item_cgst = Decimal('0.00')
            item_sgst = Decimal('0.00')
            item_gst_amount = Decimal('0.00')
            item_total_with_tax = item_subtotal + item_igst
            total_igst += item_igst
        else:
            gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
            item_gst_amount = item_subtotal * gst_rate_decimal
            item_cgst = item_gst_amount / Decimal('2')
            item_sgst = item_gst_amount / Decimal('2')
            item_igst = Decimal('0.00')
            item_total_with_tax = item_subtotal + item_gst_amount
            total_gst += item_gst_amount
        
        subtotal += item_subtotal
        
        item_data = {
            'cart_item': item,
            'product': product,
            'quantity': item.quantity,
            'unit_price': effective_price,
            'subtotal': item_subtotal,
            'gst_rate': product.gst,
            'igst_rate': product.igst,
            'uses_igst': uses_igst,
            'cgst_amount': item_cgst,
            'sgst_amount': item_sgst,
            'gst_amount': item_gst_amount,
            'igst_amount': item_igst,
            'total_with_gst': item_total_with_tax,
            'transaction_date': item.transaction_date,
        }
        cart_items_with_gst.append(item_data)
    
    total_amount = subtotal + total_gst + total_igst

    return render(request, 'cart.html', {
        'cart_items_with_gst': cart_items_with_gst,
        'subtotal': subtotal,
        'total_gst': total_gst,
        'total_igst': total_igst,
        'total_amount': total_amount,
        'store_owner': store_owner,
        'customer': customer,
    })


@require_POST
def remove_from_cart_view(request, username, cart_item_id):
    """Remove a single cart line for the logged-in store customer."""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)

    if not customer:
        return redirect('customer_login', username=username)

    cart_item = get_object_or_404(
        Cart,
        id=cart_item_id,
        store_owner=store_owner,
        customer=customer,
    )
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f'Removed "{product_name}" from your cart.')
    return redirect('cart_view', username=username)


def checkout_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    Cart.objects.filter(
        store_owner=store_owner,
        customer=customer,
        product__is_archived=True,
    ).delete()

    cart_items = Cart.objects.filter(store_owner=store_owner, customer=customer)
    if not cart_items.exists():
        return redirect('cart_view', username=username)

    # Calculate totals with GST/IGST breakdown
    subtotal = Decimal('0.00')
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')
    total_igst = Decimal('0.00')
    
    for item in cart_items:
        effective_price = item.unit_price if item.unit_price > 0 else item.product.price
        item_subtotal = effective_price * item.quantity
        product = item.product
        uses_igst = product.igst is not None and product.igst > 0
        
        if uses_igst:
            igst_rate = Decimal(str(product.igst)) / Decimal('100')
            item_igst = item_subtotal * igst_rate
            total_igst += item_igst
        else:
            gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
            item_total_gst = item_subtotal * gst_rate_decimal
            total_cgst += item_total_gst / Decimal('2')
            total_sgst += item_total_gst / Decimal('2')
        
        subtotal += item_subtotal

    total_gst = total_cgst + total_sgst
    grand_total = subtotal + total_gst + total_igst

    line_dates = [c.transaction_date for c in cart_items if getattr(c, 'transaction_date', None)]
    invoice_date = max(line_dates) if line_dates else timezone.now().date()

    order = Order.objects.create(
        store_owner=store_owner,
        customer=customer,
        total_price=grand_total,
        subtotal=subtotal,
        total_cgst=total_cgst,
        total_sgst=total_sgst,
        total_gst=total_gst,
        total_igst=total_igst,
        status='pending',
        invoice_date=invoice_date,
    )

    order.invoice_number = f"{order.order_number:04d}"
    order.save()

    # Create order items with GST/IGST breakdown
    for item in cart_items:
        effective_price = item.unit_price if item.unit_price > 0 else item.product.price
        item_subtotal = effective_price * item.quantity
        product = item.product
        uses_igst = product.igst is not None and product.igst > 0
        
        if uses_igst:
            igst_rate = Decimal(str(product.igst)) / Decimal('100')
            item_igst = item_subtotal * igst_rate
            item_cgst = Decimal('0.00')
            item_sgst = Decimal('0.00')
            item_gst = Decimal('0.00')
            item_total = item_subtotal + item_igst
        else:
            gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
            item_gst = item_subtotal * gst_rate_decimal
            item_cgst = item_gst / Decimal('2')
            item_sgst = item_gst / Decimal('2')
            item_igst = Decimal('0.00')
            item_total = item_subtotal + item_gst
        
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item.quantity,
            item_price=effective_price,
            total_price=item_total,
            subtotal=item_subtotal,
            cgst_amount=item_cgst,
            sgst_amount=item_sgst,
            gst_amount=item_gst,
            igst_amount=item_igst,
        )

        product.quantity -= item.quantity
        product.save()

        sale_day = item.transaction_date or invoice_date
        sale_dt = timezone.make_aware(datetime.combine(sale_day, time(12, 0, 0)))
        SalesReport.objects.create(
            store_owner=store_owner,
            customer=customer,
            product=product,
            order=order,
            quantity=item.quantity,
            total_price=item_total,
            profit=Decimal('0.00'),
            category=product.category or 'Uncategorized',
            sale_date=sale_dt,
        )

    cart_items.delete()
    return redirect('my_orders', username=username)


def my_orders_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    # Filter out deleted orders by default
    orders = Order.objects.filter(
        store_owner=store_owner, 
        customer=customer,
        is_deleted=False
    ).order_by('-order_date')
    
    return render(request, 'my_orders.html', {
        'orders': orders,
        'store_owner': store_owner,
        'customer': customer,
    })

def order_detail_view(request, username, order_id):
    """View detailed information about a specific order"""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    # Get the order - ensure it belongs to the customer and store owner
    order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)
    
    # Get all order items
    order_items = order.items.all()
    
    # Calculate GST/IGST breakdown for display
    updated_items = []
    for item in order_items:
        item_subtotal = item.item_price * item.quantity
        product = item.product
        uses_igst = product.igst is not None and product.igst > 0
        
        if uses_igst:
            igst_rate = Decimal(str(product.igst)) / Decimal('100')
            item_igst = item_subtotal * igst_rate
            item_cgst = Decimal('0.00')
            item_sgst = Decimal('0.00')
            item_gst = Decimal('0.00')
            item_total_with_tax = item_subtotal + item_igst
        else:
            gst_rate = Decimal(str(product.gst))
            gst_decimal = gst_rate / Decimal('100')
            item_gst = item_subtotal * gst_decimal
            item_cgst = item_gst / Decimal('2')
            item_sgst = item_gst / Decimal('2')
            item_igst = Decimal('0.00')
            item_total_with_tax = item_subtotal + item_gst
        
        item_data = {
            'item': item,
            'product': product,
            'quantity': item.quantity,
            'unit_price': item.item_price,
            'subtotal': item_subtotal,
            'gst_rate': product.gst,
            'igst_rate': product.igst,
            'uses_igst': uses_igst,
            'cgst_amount': item_cgst,
            'sgst_amount': item_sgst,
            'gst_amount': item_gst,
            'igst_amount': item_igst,
            'total_with_gst': item_total_with_tax,
        }
        updated_items.append(item_data)

    context = {
        'order': order,
        'order_items': updated_items,
        'store_owner': store_owner,
        'customer': customer,
    }
    
    return render(request, 'order_detail.html', context)

# -------------------- STORE OWNER VIEWS --------------------

@login_required
def sales_report_view(request):
    """Sales report for the logged-in store owner"""
    user = request.user
    sales = SalesReport.objects.filter(store_owner=user, order__is_deleted=False).order_by('-sale_date')
    total_sales = sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    total_revenue = total_sales

    return render(request, 'sales_report.html', {
        'sales': sales,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
    })


@login_required
def customer_details_list_view(request):
    """All shop customers for the logged-in store owner (Bootstrap table)."""
    customers = ShopCustomer.objects.filter(store_owner=request.user).order_by('name', 'phone')
    return render(request, 'customer_details.html', {'customers': customers})


@login_required
def sales_dashboard_view(request):
    """Sales dashboard for the logged-in store owner"""
    user = request.user
    sales = SalesReport.objects.filter(store_owner=user, order__is_deleted=False)
    
    total_sales = sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    total_revenue = total_sales
    total_orders = Order.objects.filter(store_owner=user, is_deleted=False).count()
    
    # Category-wise sales
    category_sales = sales.values('category').annotate(
        total=Sum('total_price'),
        quantity_sold=Sum('quantity')
    ).order_by('-total')

    return render(request, 'sales_dashboard.html', {
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'category_sales': category_sales,
    })

# -------------------- INVOICE GENERATION WITH GST --------------------

def _compute_invoice_line_items(order):
    """Attach per-line subtotals/GST/IGST to items; set order subtotal/total_* fields."""
    invoice_items = order.items.all()
    updated_items = []
    gst_summary = {}
    order_subtotal = Decimal('0.00')
    order_total_cgst = Decimal('0.00')
    order_total_sgst = Decimal('0.00')
    order_total_igst = Decimal('0.00')
    for item in invoice_items:
        item_subtotal = item.item_price * item.quantity
        product = item.product
        uses_igst = product.igst is not None and product.igst > 0
        
        if uses_igst:
            igst_rate = Decimal(str(product.igst))
            igst_decimal = igst_rate / Decimal('100')
            item_igst = item_subtotal * igst_decimal
            item.subtotal = item_subtotal
            item.cgst_amount = Decimal('0.00')
            item.sgst_amount = Decimal('0.00')
            item.gst_amount = Decimal('0.00')
            item.igst_amount = item_igst
            order_total_igst += item_igst
            # Add to summary under IGST key
            key = f'IGST_{float(igst_rate)}'
            if key not in gst_summary:
                gst_summary[key] = {
                    'rate': float(igst_rate),
                    'tax_type': 'IGST',
                    'taxable_amount': Decimal('0.00'),
                    'cgst': Decimal('0.00'),
                    'sgst': Decimal('0.00'),
                    'igst': Decimal('0.00'),
                    'total_gst': Decimal('0.00'),
                }
            gst_summary[key]['taxable_amount'] += item_subtotal
            gst_summary[key]['igst'] += item_igst
            gst_summary[key]['total_gst'] += item_igst
        else:
            gst_rate = Decimal(str(product.gst))
            gst_decimal = gst_rate / Decimal('100')
            item_total_gst = item_subtotal * gst_decimal
            item_cgst = item_total_gst / Decimal('2')
            item_sgst = item_total_gst / Decimal('2')
            item.subtotal = item_subtotal
            item.cgst_amount = item_cgst
            item.sgst_amount = item_sgst
            item.gst_amount = item_total_gst
            item.igst_amount = Decimal('0.00')
            order_total_cgst += item_cgst
            order_total_sgst += item_sgst
            gst_rate_float = float(gst_rate)
            key = f'GST_{gst_rate_float}'
            if key not in gst_summary:
                gst_summary[key] = {
                    'rate': gst_rate_float,
                    'tax_type': 'GST',
                    'taxable_amount': Decimal('0.00'),
                    'cgst': Decimal('0.00'),
                    'sgst': Decimal('0.00'),
                    'igst': Decimal('0.00'),
                    'total_gst': Decimal('0.00'),
                }
            gst_summary[key]['taxable_amount'] += item_subtotal
            gst_summary[key]['cgst'] += item_cgst
            gst_summary[key]['sgst'] += item_sgst
            gst_summary[key]['total_gst'] += item_total_gst
        
        updated_items.append(item)
        order_subtotal += item_subtotal
    order.subtotal = order_subtotal
    order.total_cgst = order_total_cgst
    order.total_sgst = order_total_sgst
    order.total_gst = order_total_cgst + order_total_sgst
    order.total_igst = order_total_igst
    return updated_items, gst_summary


def build_invoice_context(store_owner, order, *, as_pdf=False):
    company_details = store_owner.get_company_details()
    company = type('Company', (), company_details)()
    updated_items, gst_summary = _compute_invoice_line_items(order)
    order.get_amount_in_words = lambda: f"Rupees {int(order.total_price)} Only"
    if not getattr(order, 'invoice_number', None):
        order.invoice_number = f"INV-{order.id}-{order.order_date.strftime('%Y%m')}"
    total_gst = order.total_gst if order.total_gst is not None else Decimal('0')
    return {
        'order': order,
        'invoice': order,
        'company': company,
        'customer': order.customer,
        'store_owner': store_owner,
        'invoice_items': updated_items,
        'gst_summary': list(gst_summary.values()),
        'gst_total': total_gst,
        'show_gst_summary': total_gst > 0,
        'as_pdf': as_pdf,
    }


def _resolve_invoice_order(request, username, order_id):
    store_owner = get_store_owner(username)
    if hasattr(request.user, 'username') and request.user.username == username:
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner)
        return order, store_owner, None
    customer = get_logged_in_customer(request, store_owner)
    if not customer:
        return None, store_owner, redirect('customer_login', username=username)
    order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)
    return order, store_owner, None


def _invoice_html_to_pdf_xhtml2pdf(html_string: str) -> bytes:
    """Render invoice HTML to PDF using xhtml2pdf (pure Python, no browser needed)."""
    from io import BytesIO
    from xhtml2pdf import pisa

    result_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_string, dest=result_buffer)
    if pisa_status.err:
        raise RuntimeError(f'xhtml2pdf conversion error (code {pisa_status.err})')
    return result_buffer.getvalue()


def _invoice_html_to_pdf_playwright(html_string: str, base_url: str) -> bytes:
    """Render invoice HTML to PDF with headless Chromium (Playwright). Fallback option."""
    if re.search(r'<base\s', html_string, re.IGNORECASE) is None:
        safe_href = html_stdlib.escape(base_url, quote=True)
        html_string = re.sub(
            r'(<head[^>]*>)',
            rf'\1<base href="{safe_href}">',
            html_string,
            count=1,
            flags=re.IGNORECASE,
        )
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html_string, wait_until='load', timeout=60_000)
            return page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '7mm', 'right': '9mm', 'bottom': '7mm', 'left': '9mm'},
            )
        finally:
            browser.close()


def generate_invoice_view(request, username, order_id):
    """Generate HTML invoice for an order with CGST/SGST breakdown."""
    order, store_owner, err = _resolve_invoice_order(request, username, order_id)
    if err:
        return err
    context = build_invoice_context(store_owner, order, as_pdf=False)
    return render(request, 'invoice_template.html', context)


def generate_invoice_pdf(request, username, order_id):
    """Generate PDF invoice. Uses xhtml2pdf (primary) with Playwright as fallback."""
    order, store_owner, err = _resolve_invoice_order(request, username, order_id)
    if err:
        return err
    context = build_invoice_context(store_owner, order, as_pdf=True)
    html_string = render_to_string('invoice_template.html', context, request=request)

    # Try Playwright first for pixel-perfect rendering
    base = request.build_absolute_uri('/')
    try:
        pdf_bytes = _invoice_html_to_pdf_playwright(html_string, base)
    except Exception as playwright_err:
        # Fallback to xhtml2pdf if Playwright fails
        try:
            pdf_bytes = _invoice_html_to_pdf_xhtml2pdf(html_string)
        except Exception as xhtml_err:
            return HttpResponse(
                f'Could not generate PDF.<br>'
                f'Playwright error: {str(playwright_err)}<br>'
                f'xhtml2pdf error: {str(xhtml_err)}<br><br>'
                f'<strong>Tip:</strong> Open the invoice in your browser, '
                f'click Print, and select "Save as PDF".',
                status=503,
            )

    inv = getattr(order, 'invoice_number', None) or f'INV-{order.id}'
    safe_inv = ''.join(c if c.isalnum() or c in '-_' else '_' for c in str(inv))
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{safe_inv}.pdf"'
    return response


# This is the existing generate_invoice function as well used for backward compatibility
def generate_invoice(request, username, order_id):
    """Backward compatibility - redirect to PDF generation"""
    return generate_invoice_pdf(request, username, order_id)


@require_POST
def delete_invoice(request, username, order_id):
    """Delete an invoice (soft delete) and restore stock"""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)
    
    order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)
    
    # Prevent double deletion
    if not order.is_deleted:
        # Restore stock for each order item
        for item in order.items.all():
            product = item.product
            product.quantity += item.quantity
            product.save()
        
        # Mark order as deleted
        order.is_deleted = True
        order.save()
        
        messages.success(request, f'Invoice {order.invoice_number or order.order_number} has been deleted and stock has been restored.')
    else:
        messages.warning(request, 'This invoice has already been deleted.')
    
    return redirect('my_orders', username=username)


@require_POST
def restore_invoice(request, username, order_id):
    """Restore a deleted invoice and deduct stock"""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)
    
    order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)
    
    # Only restore if it's deleted
    if order.is_deleted:
        # Deduct stock for each order item
        for item in order.items.all():
            product = item.product
            if product.quantity >= item.quantity:
                product.quantity -= item.quantity
                product.save()
            else:
                messages.error(request, f'Cannot restore: Insufficient stock for {product.name}.')
                return redirect('deleted_invoices', username=username)
        
        # Unmark order as deleted
        order.is_deleted = False
        order.save()
        
        messages.success(request, f'Invoice {order.invoice_number or order.order_number} has been restored.')
    else:
        messages.warning(request, 'This invoice is not deleted.')
    
    return redirect('deleted_invoices', username=username)


def deleted_invoices_view(request, username):
    """View deleted invoices for a customer"""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)
    
    # Show only deleted orders for this customer
    orders = Order.objects.filter(
        store_owner=store_owner, 
        customer=customer,
        is_deleted=True
    ).order_by('-order_date')
    
    return render(request, 'deleted_invoices.html', {
        'orders': orders,
        'store_owner': store_owner,
        'customer': customer,
        'user': store_owner,
    })


@login_required
def analytics_dashboard_view(request):
    """
    Render the analytics dashboard template
    """
    return render(request, 'analytics_dashboard.html', {
        'user': request.user,
        'username': request.user.username,
        'page_title': 'Item Analytics Dashboard',
    })
    
    
# -------------------- USER ANALYTICS DASHBOARD --------------------
@login_required
def user_analytics_dashboard_view(request, username):
    """
    Render the analytics dashboard template for a specific user
    Only the store owner can access their own analytics
    """
    try:
        # Get the store owner by username
        store_owner = get_object_or_404(CustomUser, username=username)
        
        # Security check: Only allow store owners to access their own analytics
        if request.user != store_owner:
            return render(request, 'error.html', {
                'error_message': 'Access denied. You can only view your own analytics.',
                'error_code': 403
            }, status=403)
        
        return render(request, 'user_analytics_dashboard.html', {
            'user': request.user,
            'store_owner': store_owner,
            'username': username,
            'page_title': f'{username} - Item Analytics Dashboard'
        })
        
    except Exception as e:
        return render(request, 'error.html', {
            'error_message': f'Error loading analytics dashboard: {str(e)}',
            'error_code': 500
        }, status=500)
    
    

# ------- Monthly Report Code ------

import csv

@login_required
def monthly_stock_report(request):
    """Monthly stock report (includes archived products for analytics integrity)."""
    user = request.user
    current_date = timezone.now()

    year = int(request.GET.get('year', current_date.year))
    month = int(request.GET.get('month', current_date.month))

    products = Product.objects.filter(store_owner=user)

    stock_details = []
    total_taxable_stock_value = Decimal('0.00')
    total_stock_value = Decimal('0.00')
    total_sales_value = Decimal('0.00')
    total_gst_collected = Decimal('0.00')
    total_igst_collected = Decimal('0.00')

    for product in products:
        detail = _stock_detail_for_product(user, product, year, month)
        stock_details.append(detail)
        total_taxable_stock_value += detail['taxable_stock_value']
        total_stock_value += detail['total_stock_value']
        total_sales_value += detail['sales_amount']
        total_gst_collected += detail['gst_amount']
        total_igst_collected += detail['igst_amount']

    category_summary = {}
    for detail in stock_details:
        category = detail['category']
        if category not in category_summary:
            category_summary[category] = {
                'total_products': 0, 'total_stock': 0, 'total_sold': 0,
                'total_sales_value': Decimal('0.00'), 'total_stock_value': Decimal('0.00'),
                'total_gst_collected': Decimal('0.00'), 'total_igst_collected': Decimal('0.00'),
                'out_of_stock_count': 0, 'low_stock_count': 0,
            }

        category_summary[category]['total_products'] += 1
        category_summary[category]['total_stock'] += detail['current_stock']
        category_summary[category]['total_sold'] += detail['sold_quantity']
        category_summary[category]['total_sales_value'] += detail['sales_amount']
        category_summary[category]['total_stock_value'] += detail['total_stock_value']
        category_summary[category]['total_gst_collected'] += detail['gst_amount']
        category_summary[category]['total_igst_collected'] += detail['igst_amount']

        if detail['stock_status'] == 'Out of Stock':
            category_summary[category]['out_of_stock_count'] += 1
        elif detail['stock_status'] == 'Low Stock':
            category_summary[category]['low_stock_count'] += 1

    month_name = calendar.month_name[month]

    export_headers = [
        'Product Name', 'Category', 'GST %', 'HSN', 'Batch No', 'Quantity (stock)', 'Measurement Type',
        'Initial Stock', 'Current Stock', 'Units Sold',
        'Unit Price (Rs)', 'Sales Amount (Rs)', 'GST Amount (Rs)', 'Total Amount (Rs)', 'Stock Value (Rs)', 'Status',
    ]

    if request.GET.get('format') == 'xlsx':
        rows = []
        for detail in stock_details:
            p = detail['product']
            up = p.unit_amount if p.unit_amount and p.unit_amount > 0 else p.price
            rows.append([
                p.name,
                p.category or '',
                str(p.gst),
                p.hsn_code or '',
                p.batch_number or '',
                p.quantity,
                p.get_measurement_type_display(),
                detail['initial_stock'],
                detail['current_stock'],
                detail['sold_quantity'],
                f"{up:.2f}",
                f"{detail['sales_amount']:.2f}",
                f"{detail['gst_amount']:.2f}",
                f"{detail['total_amount_with_gst']:.2f}",
                f"{detail['stock_value']:.2f}",
                detail['stock_status'],
            ])
        buf, fname = build_workbook_response(
            f'monthly_stock_{month_name}_{year}.xlsx',
            f'Monthly {month_name}'[:31],
            export_headers,
            rows,
        )
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f'monthly_stock_report_{month_name}_{year}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(['Monthly Stock Report', f'{month_name} {year}'])
        writer.writerow(['Store Owner:', user.company_name or user.username])
        writer.writerow(['Report Generated:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        writer.writerow(['SUMMARY'])
        writer.writerow(['Total Stock Value:', f'Rs{total_stock_value:.2f}'])
        writer.writerow(['Monthly Sales:', f'Rs{total_sales_value:.2f}'])
        writer.writerow(['Total GST Collected:', f'Rs{total_gst_collected:.2f}'])
        writer.writerow(['Total Products:', len(stock_details)])
        writer.writerow([])
        writer.writerow(export_headers)
        for detail in stock_details:
            p = detail['product']
            up = p.unit_amount if p.unit_amount and p.unit_amount > 0 else p.price
            writer.writerow([
                p.name, p.category or '', str(p.gst), p.hsn_code or '', p.batch_number or '',
                p.quantity, p.get_measurement_type_display(),
                detail['initial_stock'], detail['current_stock'], detail['sold_quantity'],
                f"{up:.2f}", f"{detail['sales_amount']:.2f}", f"{detail['gst_amount']:.2f}",
                f"{detail['total_amount_with_gst']:.2f}", f"{detail['stock_value']:.2f}", detail['stock_status'],
            ])
        return response

    context = {
        'stock_details': stock_details,
        'category_summary': category_summary,
        'year': year,
        'month': month,
        'month_name': month_name,
        'total_taxable_stock_value': total_taxable_stock_value,
        'total_stock_value': total_stock_value,
        'total_sales_value': total_sales_value,
        'total_gst_collected': total_gst_collected,
        'total_igst_collected': total_igst_collected,
        'report_date': f'{month_name} {year}',
        'user': user,
        'prev_month': month - 1 if month > 1 else 12,
        'prev_year': year if month > 1 else year - 1,
        'next_month': month + 1 if month < 12 else 1,
        'next_year': year if month < 12 else year + 1,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': list(range(2020, current_date.year + 2)),
    }

    return render(request, 'monthly_stock_report.html', context)


#------- Yearly Report Code -------

@login_required
def yearly_stock_summary(request):
    """Yearly overview plus per-product stock detail (same columns as monthly, aggregated by year)."""
    user = request.user
    current_date = timezone.now()
    year = int(request.GET.get('year', current_date.year))

    monthly_data = []
    for month in range(1, 13):
        try:
            month_sales = SalesReport.objects.filter(
                store_owner=user,
                sale_date__year=year,
                sale_date__month=month,
            )
            total_sales = month_sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
            total_quantity_sold = month_sales.aggregate(qty=Sum('quantity'))['qty'] or 0

            total_gst = Decimal('0.00')
            for sale in month_sales:
                if sale.product.gst > 0:
                    gst_rate = Decimal(str(sale.product.gst)) / Decimal('100')
                    base_amount = sale.total_price / (Decimal('1') + gst_rate)
                    sale_gst = sale.total_price - base_amount
                    total_gst += sale_gst

        except Exception:
            month_orders = Order.objects.filter(
                store_owner=user,
                order_date__year=year,
                order_date__month=month,
            )

            total_sales = Decimal('0.00')
            total_gst = Decimal('0.00')
            total_quantity_sold = 0

            for order in month_orders:
                total_sales += order.total_price or Decimal('0.00')
                total_gst += getattr(order, 'total_gst', Decimal('0.00'))

                for item in order.items.all():
                    total_quantity_sold += item.quantity

        monthly_data.append({
            'month': month,
            'month_name': calendar.month_name[month],
            'total_sales': total_sales,
            'total_gst': total_gst,
            'quantity_sold': total_quantity_sold,
        })

    yearly_sales = sum(data['total_sales'] for data in monthly_data)
    yearly_gst = sum(data['total_gst'] for data in monthly_data)
    yearly_quantity = sum(data['quantity_sold'] for data in monthly_data)

    products = Product.objects.filter(store_owner=user)
    stock_details = []
    total_taxable_stock_value = Decimal('0.00')
    total_stock_value = Decimal('0.00')
    total_sales_value = Decimal('0.00')
    total_gst_collected = Decimal('0.00')
    total_igst_collected = Decimal('0.00')

    for product in products:
        detail = _stock_detail_for_product(user, product, year, None)
        stock_details.append(detail)
        total_taxable_stock_value += detail['taxable_stock_value']
        total_stock_value += detail['total_stock_value']
        total_sales_value += detail['sales_amount']
        total_gst_collected += detail['gst_amount']
        total_igst_collected += detail['igst_amount']

    category_summary = {}
    for detail in stock_details:
        category = detail['category']
        if category not in category_summary:
            category_summary[category] = {
                'total_products': 0, 'total_stock': 0, 'total_sold': 0,
                'total_sales_value': Decimal('0.00'), 'total_stock_value': Decimal('0.00'),
                'total_gst_collected': Decimal('0.00'), 'total_igst_collected': Decimal('0.00'),
                'out_of_stock_count': 0, 'low_stock_count': 0,
            }

        category_summary[category]['total_products'] += 1
        category_summary[category]['total_stock'] += detail['current_stock']
        category_summary[category]['total_sold'] += detail['sold_quantity']
        category_summary[category]['total_sales_value'] += detail['sales_amount']
        category_summary[category]['total_stock_value'] += detail['total_stock_value']
        category_summary[category]['total_gst_collected'] += detail['gst_amount']
        category_summary[category]['total_igst_collected'] += detail['igst_amount']

        if detail['stock_status'] == 'Out of Stock':
            category_summary[category]['out_of_stock_count'] += 1
        elif detail['stock_status'] == 'Low Stock':
            category_summary[category]['low_stock_count'] += 1

    export_headers = [
        'Product Name', 'Category', 'GST %', 'IGST %', 'HSN', 'Batch No', 'Quantity (stock)', 'Measurement Type',
        'Initial Stock', 'Current Stock', 'Units Sold',
        'Sales Amount (Rs)', 'IGST (Rs)', 'CGST (Rs)', 'SGST (Rs)',
        'Taxable Stock Value (Rs)', 'Total Stock Value (Rs)', 'Status',
    ]

    if request.GET.get('format') == 'xlsx':
        rows = []
        for detail in stock_details:
            p = detail['product']
            rows.append([
                p.name, p.category or '', str(p.gst), str(p.igst), p.hsn_code or '', p.batch_number or '',
                p.quantity, p.get_measurement_type_display(),
                detail['initial_stock'], detail['current_stock'], detail['sold_quantity'],
                f"{detail['sales_amount']:.2f}",
                f"{detail['igst_amount']:.2f}", f"{detail['cgst_amount']:.2f}", f"{detail['sgst_amount']:.2f}",
                f"{detail['taxable_stock_value']:.2f}", f"{detail['total_stock_value']:.2f}", detail['stock_status'],
            ])
        buf, fname = build_workbook_response(
            f'yearly_stock_{year}.xlsx',
            f'Yearly {year}'[:31],
            export_headers,
            rows,
        )
        response = HttpResponse(
            buf.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f'yearly_summary_{year}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(['Yearly Stock/Sales Summary', str(year)])
        writer.writerow(['Store Owner:', user.company_name or user.username])
        writer.writerow([])
        writer.writerow(['YEARLY TOTALS'])
        writer.writerow(['Total Sales:', f'Rs{yearly_sales:.2f}'])
        writer.writerow(['Total GST Collected:', f'Rs{yearly_gst:.2f}'])
        writer.writerow(['Units Sold:', yearly_quantity])
        writer.writerow([])
        writer.writerow(['MONTHLY BREAKDOWN'])
        writer.writerow(['Month', 'Sales (Rs)', 'GST Collected (Rs)', 'Units Sold'])
        for data in monthly_data:
            writer.writerow([
                data['month_name'], f"{data['total_sales']:.2f}",
                f"{data['total_gst']:.2f}", data['quantity_sold'],
            ])
        writer.writerow([])
        writer.writerow(['PRODUCT DETAILS (YEAR)'])
        writer.writerow(export_headers)
        for detail in stock_details:
            p = detail['product']
            writer.writerow([
                p.name, p.category or '', str(p.gst), str(p.igst), p.hsn_code or '', p.batch_number or '',
                p.quantity, p.get_measurement_type_display(),
                detail['initial_stock'], detail['current_stock'], detail['sold_quantity'],
                f"{detail['sales_amount']:.2f}",
                f"{detail['igst_amount']:.2f}", f"{detail['cgst_amount']:.2f}", f"{detail['sgst_amount']:.2f}",
                f"{detail['taxable_stock_value']:.2f}", f"{detail['total_stock_value']:.2f}", detail['stock_status'],
            ])
        return response

    context = {
        'monthly_data': monthly_data,
        'stock_details': stock_details,
        'category_summary': category_summary,
        'year': year,
        'yearly_sales': yearly_sales,
        'yearly_gst': yearly_gst,
        'yearly_quantity': yearly_quantity,
        'total_taxable_stock_value': total_taxable_stock_value,
        'total_stock_value': total_stock_value,
        'total_sales_value': total_sales_value,
        'total_gst_collected': total_gst_collected,
        'total_igst_collected': total_igst_collected,
        'user': user,
        'years': list(range(2020, current_date.year + 2)),
    }

    return render(request, 'yearly_stock_summary.html', context)