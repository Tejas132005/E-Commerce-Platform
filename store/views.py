# store/views.py - Complete updated file with invoice functionality

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.http import HttpResponse, Http404
from .models import Product, Cart, Order, OrderItem, SalesReport, ShopCustomer
from .forms import AddProductForm, UpdateProductForm, DeleteProductForm, CustomerLoginForm, CustomerRegisterForm
from accounts.models import CustomUser
from collections import defaultdict
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from decimal import Decimal

# -------------------- HELPER FUNCTIONS --------------------

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
    import os
    from django.conf import settings
    
    # Debug template loading
    template_path = os.path.join(settings.BASE_DIR, 'templates', 'store_products.html')
    print(f"Looking for template at: {template_path}")
    print(f"Template exists: {os.path.exists(template_path)}")
    print(f"BASE_DIR: {settings.BASE_DIR}")
    
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    # Get products and add debugging
    products = Product.objects.filter(store_owner=store_owner).order_by('category', 'name')
    
    # DEBUGGING: Print product information
    print("="*50)
    print("PRODUCTS DEBUG")
    print("="*50)
    print(f"Store owner: {store_owner.username}")
    print(f"Total products found: {products.count()}")
    
    for product in products:
        print(f"Product: {product.name} | Category: {product.category} | Price: {product.price} | Stock: {product.quantity}")
    
    # Build categorized products as regular dict instead of defaultdict
    categorized_products = {}
    for product in products:
        category = product.category or 'Uncategorized'
        if category not in categorized_products:
            categorized_products[category] = []
        categorized_products[category].append(product)
        print(f"Added {product.name} to category: {category}")

    sorted_categories = sorted(categorized_products.keys())
    
    print(f"Categories found: {sorted_categories}")
    for category, products_in_category in categorized_products.items():
        print(f"Category '{category}' has {len(products_in_category)} products")
    
    # DEBUGGING: Print the final data structure
    print("FINAL DATA STRUCTURE:")
    print(f"categorized_products type: {type(categorized_products)}")
    print(f"categorized_products content: {categorized_products}")
    print(f"sorted_categories: {sorted_categories}")
    print("="*50)

    context = {
        'categorized_products': categorized_products,
        'sorted_categories': sorted_categories,
        'store_owner': store_owner,
        'customer': customer,
        'payment_success': request.GET.get('payment_success'),
    }

    return render(request, 'store_products.html', context)

def product_detail_view(request, username, product_id):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    product = get_object_or_404(Product, id=product_id, store_owner=store_owner)
    return render(request, 'product_detail.html', {
        'product': product,
        'store_owner': store_owner,
        'customer': customer,
    })

# -------------------- CART & BILLING WITH GST --------------------

def add_to_cart_view(request, username, product_id):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, store_owner=store_owner)
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity > product.quantity:
            # Handle insufficient stock
            return render(request, 'product_detail.html', {
                'product': product,
                'error': f'Only {product.quantity} items available in stock',
                'store_owner': store_owner,
                'customer': customer,
            })
        
        # Calculate total price WITHOUT GST for cart storage
        total_price_without_gst = product.price * quantity

        cart_item, created = Cart.objects.get_or_create(
            store_owner=store_owner,
            customer=customer,
            product=product,
            defaults={'quantity': quantity, 'total_price': total_price_without_gst}
        )

        if not created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.quantity:
                return render(request, 'product_detail.html', {
                    'product': product,
                    'error': f'Cannot add more. Only {product.quantity} items available, you already have {cart_item.quantity} in cart',
                    'store_owner': store_owner,
                    'customer': customer,
                })
            
            cart_item.quantity = new_quantity
            cart_item.total_price = product.price * cart_item.quantity
            cart_item.save()

        return redirect('cart_view', username=username)

def cart_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    cart_items = Cart.objects.filter(store_owner=store_owner, customer=customer)
    
    # Calculate totals with GST
    subtotal = Decimal('0.00')
    total_gst = Decimal('0.00')
    
    cart_items_with_gst = []
    
    for item in cart_items:
        # Calculate item subtotal (without GST)
        item_subtotal = item.product.price * item.quantity
        
        # Calculate GST for this item
        item_gst_rate = item.product.gst / 100
        item_gst_amount = item_subtotal * item_gst_rate
        
        # Calculate item total (with GST)
        item_total_with_gst = item_subtotal + item_gst_amount
        
        # Add to overall totals
        subtotal += item_subtotal
        total_gst += item_gst_amount
        
        # Create enhanced item object
        item_data = {
            'cart_item': item,
            'product': item.product,
            'quantity': item.quantity,
            'unit_price': item.product.price,
            'subtotal': item_subtotal,
            'gst_rate': item.product.gst,
            'gst_amount': item_gst_amount,
            'total_with_gst': item_total_with_gst,
        }
        cart_items_with_gst.append(item_data)
    
    # Calculate final total
    total_amount = subtotal + total_gst

    return render(request, 'cart.html', {
        'cart_items_with_gst': cart_items_with_gst,
        'subtotal': subtotal,
        'total_gst': total_gst,
        'total_amount': total_amount,
        'store_owner': store_owner,
        'customer': customer,
    })

def checkout_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    cart_items = Cart.objects.filter(store_owner=store_owner, customer=customer)
    if not cart_items.exists():
        return redirect('cart_view', username=username)

    # Calculate totals with GST breakdown
    subtotal = Decimal('0.00')
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')
    
    for item in cart_items:
        # Calculate item subtotal (without GST)
        item_subtotal = item.product.price * item.quantity
        
        # Calculate CGST and SGST for this item
        item_gst_rate = item.product.gst / 100
        item_total_gst = item_subtotal * item_gst_rate
        item_cgst = item_total_gst / 2  # CGST = GST/2
        item_sgst = item_total_gst / 2  # SGST = GST/2
        
        # Add to totals
        subtotal += item_subtotal
        total_cgst += item_cgst
        total_sgst += item_sgst

    total_gst = total_cgst + total_sgst
    grand_total = subtotal + total_gst

    # Create order with GST breakdown
    order = Order.objects.create(
        store_owner=store_owner,
        customer=customer,
        order_date=timezone.now(),
        subtotal=subtotal,
        total_cgst=total_cgst,
        total_sgst=total_sgst,
        total_gst=total_gst,
        total_price=grand_total,
        status='pending'
    )

    # Generate invoice number
    order.invoice_number = f"INV-{order.id}-{order.order_date.strftime('%Y%m')}"
    order.save()

    # Create order items with GST breakdown
    for item in cart_items:
        # Calculate GST for this item
        item_subtotal = item.product.price * item.quantity
        item_gst_rate = item.product.gst / 100
        item_total_gst = item_subtotal * item_gst_rate
        item_cgst = item_total_gst / 2
        item_sgst = item_total_gst / 2
        item_total = item_subtotal + item_total_gst
        
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            item_price=item.product.price,
            subtotal=item_subtotal,
            cgst_amount=item_cgst,
            sgst_amount=item_sgst,
            gst_amount=item_total_gst,
            total_price=item_total
        )

        # Decrease stock
        item.product.quantity -= item.quantity
        item.product.save()

        # Calculate profit (30% of subtotal, not including GST)
        profit = item_subtotal * Decimal('0.30')

        # Create sales report
        SalesReport.objects.create(
            store_owner=store_owner,
            customer=customer,
            product=item.product,
            order=order,
            quantity=item.quantity,
            total_price=item_total,
            profit=profit,
            category=item.product.category or 'Uncategorized',
            sale_date=timezone.now()
        )

    # Clear cart
    cart_items.delete()
    return redirect('my_orders', username=username)

def my_orders_view(request, username):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    orders = Order.objects.filter(store_owner=store_owner, customer=customer).order_by('-order_date')
    return render(request, 'my_orders.html', {
        'orders': orders,
        'store_owner': store_owner,
        'customer': customer,
    })

def order_detail_view(request, username, order_id):
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)
    items = order.items.all()
    return render(request, 'order_detail.html', {
        'order': order,
        'items': items,
        'store_owner': store_owner,
        'customer': customer,
    })

# -------------------- STORE OWNER VIEWS --------------------

@login_required
def sales_report_view(request):
    """Sales report for the logged-in store owner"""
    user = request.user
    sales = SalesReport.objects.filter(store_owner=user).order_by('-sale_date')
    total_sales = sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    total_profit = sales.aggregate(profit=Sum('profit'))['profit'] or Decimal('0.00')

    return render(request, 'sales_report.html', {
        'sales': sales,
        'total_sales': total_sales,
        'total_profit': total_profit,
    })

@login_required
def sales_dashboard_view(request):
    """Sales dashboard for the logged-in store owner"""
    user = request.user
    sales = SalesReport.objects.filter(store_owner=user)
    
    total_sales = sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    total_profit = sales.aggregate(profit=Sum('profit'))['profit'] or Decimal('0.00')
    total_orders = Order.objects.filter(store_owner=user).count()
    
    # Category-wise sales
    category_sales = sales.values('category').annotate(
        total=Sum('total_price'),
        quantity_sold=Sum('quantity')
    ).order_by('-total')

    return render(request, 'sales_dashboard.html', {
        'total_sales': total_sales,
        'total_profit': total_profit,
        'total_orders': total_orders,
        'category_sales': category_sales,
    })

# -------------------- INVOICE GENERATION WITH GST --------------------

def generate_invoice_view(request, username, order_id):
    """Generate HTML invoice for an order with CGST/SGST breakdown"""
    store_owner = get_store_owner(username)
    
    # Allow both customers and store owners to generate invoices
    if hasattr(request.user, 'username') and request.user.username == username:
        # Store owner accessing their own order
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner)
    else:
        # Customer accessing their order
        customer = get_logged_in_customer(request, store_owner)
        if not customer:
            return redirect('customer_login', username=username)
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)

    # Get or create company profile
    company = {
        'name': store_owner.company_name or store_owner.username,
        'address': getattr(store_owner, 'address', 'Company Address'),
        'city': getattr(store_owner, 'city', 'City'),
        'state': getattr(store_owner, 'state', 'State'),
        'pincode': getattr(store_owner, 'pincode', '000000'),
        'phone': getattr(store_owner, 'phone', '+91-XXXXXXXXXX'),
        'email': getattr(store_owner, 'email', store_owner.email or 'info@company.com'),
        'gstin': getattr(store_owner, 'gstin', 'XXXXXXXXXXXXXXXXXXXX'),
        'jurisdiction': getattr(store_owner, 'jurisdiction', 'Local'),
    }

    # Get all order items
    invoice_items = order.items.all()
    
    # Create GST summary by rate
    gst_summary = {}
    for item in invoice_items:
        rate = item.product.gst
        if rate not in gst_summary:
            gst_summary[rate] = {
                'rate': rate,
                'taxable_amount': Decimal('0.00'),
                'cgst': Decimal('0.00'),
                'sgst': Decimal('0.00'),
                'total_gst': Decimal('0.00')
            }
        
        gst_summary[rate]['taxable_amount'] += item.subtotal
        gst_summary[rate]['cgst'] += item.cgst_amount
        gst_summary[rate]['sgst'] += item.sgst_amount
        gst_summary[rate]['total_gst'] += item.gst_amount

    context = {
        'order': order,
        'invoice': order,  # Alias for template compatibility
        'company': type('Company', (), company)(),  # Convert dict to object
        'customer': order.customer,
        'store_owner': store_owner,
        'invoice_items': invoice_items,
        'gst_summary': gst_summary.values(),
    }

    return render(request, 'invoice_template.html', context)

# Add these functions to your existing store/views.py
# These work with your current models and add invoice functionality

from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import HttpResponse
from .models import Product, Cart, Order, OrderItem, SalesReport, ShopCustomer
from accounts.models import CustomUser
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from decimal import Decimal

# -------------------- ADD THESE NEW FUNCTIONS --------------------

def generate_invoice_view(request, username, order_id):
    """Generate HTML invoice for an order with CGST/SGST breakdown"""
    store_owner = get_store_owner(username)
    
    # Allow both customers and store owners to generate invoices
    if hasattr(request.user, 'username') and request.user.username == username:
        # Store owner accessing their own order
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner)
    else:
        # Customer accessing their order
        customer = get_logged_in_customer(request, store_owner)
        if not customer:
            return redirect('customer_login', username=username)
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)

    # Get company details from user profile
    company_details = store_owner.get_company_details() if hasattr(store_owner, 'get_company_details') else {
        'name': store_owner.company_name or store_owner.username,
        'address': getattr(store_owner, 'company_address', 'Company Address'),
        'city': getattr(store_owner, 'company_city', 'City'),
        'state': getattr(store_owner, 'company_state', 'State'),
        'pincode': getattr(store_owner, 'company_pincode', '000000'),
        'phone': getattr(store_owner, 'company_phone', store_owner.phone),
        'email': getattr(store_owner, 'company_email', store_owner.email),
        'gstin': getattr(store_owner, 'company_gstin', 'GSTIN not provided'),
        'jurisdiction': 'Local',
    }

    # Convert dict to object for template compatibility
    company = type('Company', (), company_details)()

    # Get all order items
    invoice_items = order.items.all()
    
    # Calculate GST breakdown for each item and create summary
    updated_items = []
    gst_summary = {}
    
    order_subtotal = Decimal('0.00')
    order_total_cgst = Decimal('0.00')
    order_total_sgst = Decimal('0.00')
    
    for item in invoice_items:
        # Calculate item subtotal
        item_subtotal = item.item_price * item.quantity
        
        # Calculate GST amounts
        gst_rate = float(item.product.gst)
        item_total_gst = item_subtotal * (gst_rate / 100)
        item_cgst = item_total_gst / 2  # CGST = GST/2
        item_sgst = item_total_gst / 2  # SGST = GST/2
        item_total_with_gst = item_subtotal + item_total_gst
        
        # Update item object with calculated values
        item.subtotal = item_subtotal
        item.cgst_amount = item_cgst
        item.sgst_amount = item_sgst
        item.gst_amount = item_total_gst
        
        updated_items.append(item)
        
        # Add to order totals
        order_subtotal += item_subtotal
        order_total_cgst += item_cgst
        order_total_sgst += item_sgst
        
        # Create GST summary by rate
        if gst_rate not in gst_summary:
            gst_summary[gst_rate] = {
                'rate': gst_rate,
                'taxable_amount': Decimal('0.00'),
                'cgst': Decimal('0.00'),
                'sgst': Decimal('0.00'),
                'total_gst': Decimal('0.00')
            }
        
        gst_summary[gst_rate]['taxable_amount'] += item_subtotal
        gst_summary[gst_rate]['cgst'] += item_cgst
        gst_summary[gst_rate]['sgst'] += item_sgst
        gst_summary[gst_rate]['total_gst'] += item_total_gst

    # Update order with calculated totals (if fields exist)
    if hasattr(order, 'subtotal'):
        order.subtotal = order_subtotal
        order.total_cgst = order_total_cgst
        order.total_sgst = order_total_sgst
        order.total_gst = order_total_cgst + order_total_sgst
    else:
        # Add attributes dynamically for template compatibility
        order.subtotal = order_subtotal
        order.total_cgst = order_total_cgst
        order.total_sgst = order_total_sgst
        order.total_gst = order_total_cgst + order_total_sgst
    
    # Add methods to order for template compatibility
    order.get_amount_in_words = lambda: f"Rupees {int(order.total_price)} Only"
    
    # Generate invoice number if not exists
    if not hasattr(order, 'invoice_number') or not order.invoice_number:
        invoice_number = f"INV-{order.id}-{order.order_date.strftime('%Y%m')}"
        order.invoice_number = invoice_number
    
    # Add payment terms if not exists
    if not hasattr(order, 'payment_terms'):
        order.payment_terms = 30

    context = {
        'order': order,
        'invoice': order,  # Alias for template compatibility
        'company': company,
        'customer': order.customer,
        'store_owner': store_owner,
        'invoice_items': updated_items,
        'gst_summary': gst_summary.values(),
    }

    return render(request, 'invoice_template.html', context)

def generate_invoice_pdf(request, username, order_id):
    """Generate PDF invoice for an order with GST breakdown"""
    store_owner = get_store_owner(username)
    
    # Allow both customers and store owners to generate invoices
    if hasattr(request.user, 'username') and request.user.username == username:
        # Store owner accessing their own order
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner)
    else:
        # Customer accessing their order
        customer = get_logged_in_customer(request, store_owner)
        if not customer:
            return redirect('customer_login', username=username)
        order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Invoice header
    p.setFont("Helvetica-Bold", 20)
    p.drawString(50, height - 50, "TAX INVOICE")
    
    # Company details
    company_name = store_owner.company_name or store_owner.username
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 80, f"{company_name}")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 100, getattr(store_owner, 'company_address', 'Company Address'))
    city_line = f"{getattr(store_owner, 'company_city', 'City')}, {getattr(store_owner, 'company_state', 'State')} - {getattr(store_owner, 'company_pincode', '000000')}"
    p.drawString(50, height - 115, city_line)
    p.drawString(50, height - 130, f"Phone: {getattr(store_owner, 'company_phone', store_owner.phone)}")
    p.drawString(50, height - 145, f"Email: {getattr(store_owner, 'company_email', store_owner.email)}")
    p.drawString(50, height - 160, f"GSTIN: {getattr(store_owner, 'company_gstin', 'GSTIN not provided')}")
    
    # Invoice details (right side)
    invoice_number = getattr(order, 'invoice_number', f'INV-{order.id}-{order.order_date.strftime("%Y%m")}')
    p.setFont("Helvetica", 10)
    p.drawString(400, height - 80, f"Invoice No: {invoice_number}")
    p.drawString(400, height - 95, f"Date: {order.order_date.strftime('%d/%m/%Y')}")
    p.drawString(400, height - 110, f"Due Date: {(order.order_date + timezone.timedelta(days=30)).strftime('%d/%m/%Y')}")
    
    # Customer details
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, height - 200, "Bill To:")
    p.setFont("Helvetica", 10)
    p.drawString(50, height - 220, f"{order.customer.name}")
    p.drawString(50, height - 235, f"Phone: {order.customer.phone}")
    
    # Customer address
    y_pos = height - 250
    if hasattr(order.customer, 'address') and order.customer.address:
        p.drawString(50, y_pos, f"{order.customer.address}")
        y_pos -= 15
    elif order.customer.place:
        p.drawString(50, y_pos, f"{order.customer.place}")
        y_pos -= 15
    
    if hasattr(order.customer, 'city') and order.customer.city:
        city_line = f"{order.customer.city}"
        if hasattr(order.customer, 'state') and order.customer.state:
            city_line += f", {order.customer.state}"
        if hasattr(order.customer, 'pincode') and order.customer.pincode:
            city_line += f" - {order.customer.pincode}"
        p.drawString(50, y_pos, city_line)
        y_pos -= 15
    
    if order.customer.email:
        p.drawString(50, y_pos, f"Email: {order.customer.email}")
        y_pos -= 15

    # Items table header
    y = height - 320
    p.setFont("Helvetica-Bold", 9)
    p.drawString(50, y, "S.No")
    p.drawString(80, y, "Description")
    p.drawString(200, y, "HSN")
    p.drawString(240, y, "Qty")
    p.drawString(270, y, "Rate")
    p.drawString(310, y, "Amount")
    p.drawString(350, y, "GST%")
    p.drawString(380, y, "CGST")
    p.drawString(420, y, "SGST")
    p.drawString(460, y, "Total")
    
    # Draw line under header
    p.line(50, y-5, 550, y-5)
    y -= 20
    
    # Items and calculations
    p.setFont("Helvetica", 8)
    subtotal = Decimal('0.00')
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')
    
    for i, item in enumerate(order.items.all(), 1):
        # Calculate GST for each item
        item_subtotal = item.item_price * item.quantity
        gst_rate = Decimal(str(item.product.gst))  # Convert to Decimal
        gst_decimal = gst_rate / Decimal('100')    # Convert percentage to decimal
        item_total_gst = item_subtotal * gst_decimal
        item_cgst = item_total_gst / 2
        item_sgst = item_total_gst / 2
        item_total = item_subtotal + item_total_gst
        
        # Add to totals
        subtotal += item_subtotal
        total_cgst += item_cgst
        total_sgst += item_sgst
        
        p.drawString(50, y, str(i))
        p.drawString(80, y, f"{item.product.name[:15]}")
        p.drawString(200, y, f"{item.product.hsn_code or 'N/A'}")
        p.drawString(240, y, str(item.quantity))
        p.drawString(270, y, f"₹{item.item_price}")
        p.drawString(310, y, f"₹{item_subtotal}")
        p.drawString(350, y, f"{gst_rate}%")
        p.drawString(380, y, f"₹{item_cgst:.2f}")
        p.drawString(420, y, f"₹{item_sgst:.2f}")
        p.drawString(460, y, f"₹{item_total:.2f}")
        y -= 15

    # Totals
    y -= 30
    p.setFont("Helvetica-Bold", 10)
    p.drawString(350, y, f"Subtotal: ₹{subtotal}")
    y -= 15
    p.drawString(350, y, f"Total CGST: ₹{total_cgst:.2f}")
    y -= 15
    p.drawString(350, y, f"Total SGST: ₹{total_sgst:.2f}")
    y -= 15
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y, f"GRAND TOTAL: ₹{order.total_price}")
    
    # Amount in words
    y -= 30
    p.setFont("Helvetica", 10)
    amount_words = f"Rupees {int(order.total_price)} Only"
    p.drawString(50, y, f"Amount in Words: {amount_words}")
    
    # Terms and signature
    y -= 40
    p.setFont("Helvetica", 8)
    p.drawString(50, y, "Terms & Conditions:")
    p.drawString(50, y-12, "• Payment is due within 30 days")
    p.drawString(50, y-24, "• Goods once sold will not be taken back")
    
    # Signature
    p.drawString(400, y-40, f"For {company_name}")
    p.drawString(400, y-80, "Authorized Signatory")

    p.showPage()
    p.save()
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice_number}.pdf"'
    return response

# -------------------- UPDATE YOUR EXISTING CHECKOUT FUNCTION --------------------

def checkout_view_updated(request, username):
    """Updated checkout with GST calculations"""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    cart_items = Cart.objects.filter(store_owner=store_owner, customer=customer)
    if not cart_items.exists():
        return redirect('cart_view', username=username)

    # Calculate totals with GST breakdown
    subtotal = Decimal('0.00')
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')
    
    for item in cart_items:
        # Calculate item subtotal (without GST)
        item_subtotal = item.product.price * item.quantity
        
        # Calculate CGST and SGST for this item
        gst_rate = float(item.product.gst)
        item_total_gst = item_subtotal * (gst_rate / 100)
        item_cgst = item_total_gst / 2  # CGST = GST/2
        item_sgst = item_total_gst / 2  # SGST = GST/2
        
        # Add to totals
        subtotal += item_subtotal
        total_cgst += item_cgst
        total_sgst += item_sgst

    total_gst = total_cgst + total_sgst
    grand_total = subtotal + total_gst

    # Create order
    order = Order.objects.create(
        store_owner=store_owner,
        customer=customer,
        order_date=timezone.now(),
        total_price=grand_total,
        status='pending'
    )

    # Add GST breakdown to order if fields exist
    if hasattr(order, 'subtotal'):
        order.subtotal = subtotal
        order.total_cgst = total_cgst
        order.total_sgst = total_sgst
        order.total_gst = total_gst
        order.save()

    # Create order items with GST calculations
    for item in cart_items:
        # Calculate GST for this item
        item_subtotal = item.product.price * item.quantity
        gst_rate = float(item.product.gst)
        item_total_gst = item_subtotal * (gst_rate / 100)
        item_cgst = item_total_gst / 2
        item_sgst = item_total_gst / 2
        item_total = item_subtotal + item_total_gst
        
        order_item = OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            item_price=item.product.price,
            total_price=item_total
        )
        
        # Add GST breakdown to order item if fields exist
        if hasattr(order_item, 'subtotal'):
            order_item.subtotal = item_subtotal
            order_item.cgst_amount = item_cgst
            order_item.sgst_amount = item_sgst
            order_item.gst_amount = item_total_gst
            order_item.save()

        # Decrease stock
        item.product.quantity -= item.quantity
        item.product.save()

        # Calculate profit (30% of subtotal, not including GST)
        profit = item_subtotal * Decimal('0.30')

        # Create sales report
        SalesReport.objects.create(
            store_owner=store_owner,
            customer=customer,
            product=item.product,
            order=order,
            quantity=item.quantity,
            total_price=item_total,
            profit=profit,
            category=item.product.category or 'Uncategorized',
            sale_date=timezone.now()
        )

    # Clear cart
    cart_items.delete()
    return redirect('my_orders', username=username)

# Keep your existing generate_invoice function as well for backward compatibility
def generate_invoice(request, username, order_id):
    """Backward compatibility - redirect to PDF generation"""
    return generate_invoice_pdf(request, username, order_id)