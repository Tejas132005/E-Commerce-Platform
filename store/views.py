# store/views.py - Complete updated file with invoice functionality and fixed decimal operations

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
from reportlab.lib.colors import HexColor, black, white
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib import colors
from decimal import Decimal

from django.db.models import Q, Case, When, IntegerField, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
import calendar

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

# -------------------- CART & BILLING WITH GST - FIXED --------------------

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
    
    # Calculate totals with GST - FIXED: Proper Decimal handling
    subtotal = Decimal('0.00')
    total_gst = Decimal('0.00')
    
    cart_items_with_gst = []
    
    for item in cart_items:
        # Calculate item subtotal (without GST)
        item_subtotal = item.product.price * item.quantity
        
        # Calculate GST for this item - FIXED: Convert to Decimal first
        gst_rate_decimal = Decimal(str(item.product.gst)) / Decimal('100')
        item_gst_amount = item_subtotal * gst_rate_decimal
        
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

    # Calculate totals with GST breakdown - FIXED: Proper Decimal handling
    subtotal = Decimal('0.00')
    total_cgst = Decimal('0.00')
    total_sgst = Decimal('0.00')
    
    for item in cart_items:
        # Calculate item subtotal (without GST)
        item_subtotal = item.product.price * item.quantity
        
        # Calculate CGST and SGST for this item - FIXED: Convert to Decimal first
        gst_rate_decimal = Decimal(str(item.product.gst)) / Decimal('100')
        item_total_gst = item_subtotal * gst_rate_decimal
        item_cgst = item_total_gst / Decimal('2')  # CGST = GST/2
        item_sgst = item_total_gst / Decimal('2')  # SGST = GST/2
        
        # Add to totals
        subtotal += item_subtotal
        total_cgst += item_cgst
        total_sgst += item_sgst

    total_gst = total_cgst + total_sgst
    grand_total = subtotal + total_gst

    # Create order - The order_number will be auto-assigned by the model's save method
    order = Order.objects.create(
        store_owner=store_owner,
        customer=customer,
        order_date=timezone.now(),
        total_price=grand_total,
        subtotal=subtotal,
        total_cgst=total_cgst,
        total_sgst=total_sgst,
        total_gst=total_gst,
        status='pending'
    )

    # Generate invoice number based on the per-user order number
    order.invoice_number = f"INV-{store_owner.username.upper()}-{order.order_number:04d}-{order.order_date.strftime('%Y%m')}"
    order.save()

    # Create order items with GST breakdown
    for item in cart_items:
        # Calculate GST for this item - FIXED: Convert to Decimal first
        item_subtotal = item.product.price * item.quantity
        gst_rate_decimal = Decimal(str(item.product.gst)) / Decimal('100')
        item_total_gst = item_subtotal * gst_rate_decimal
        item_cgst = item_total_gst / Decimal('2')
        item_sgst = item_total_gst / Decimal('2')
        item_total = item_subtotal + item_total_gst
        
        order_item = OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            item_price=item.product.price,
            total_price=item_total,
            subtotal=item_subtotal,
            cgst_amount=item_cgst,
            sgst_amount=item_sgst,
            gst_amount=item_total_gst
        )

        # Decrease stock
        item.product.quantity -= item.quantity
        item.product.save()

        # UPDATED: Calculate profit = item_subtotal (100% profit, not including GST)
        profit = item_total 

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
    """View detailed information about a specific order"""
    store_owner = get_store_owner(username)
    customer = get_logged_in_customer(request, store_owner)
    
    if not customer:
        return redirect('customer_login', username=username)

    # Get the order - ensure it belongs to the customer and store owner
    order = get_object_or_404(Order, id=order_id, store_owner=store_owner, customer=customer)
    
    # Get all order items
    order_items = order.items.all()
    
    # Calculate GST breakdown for display
    updated_items = []
    for item in order_items:
        # Calculate item subtotal
        item_subtotal = item.item_price * item.quantity
        
        # Calculate GST amounts
        gst_rate = Decimal(str(item.product.gst))
        gst_decimal = gst_rate / Decimal('100')
        item_total_gst = item_subtotal * gst_decimal
        item_cgst = item_total_gst / Decimal('2')
        item_sgst = item_total_gst / Decimal('2')
        item_total_with_gst = item_subtotal + item_total_gst
        
        # Create enhanced item object
        item_data = {
            'item': item,
            'product': item.product,
            'quantity': item.quantity,
            'unit_price': item.item_price,
            'subtotal': item_subtotal,
            'gst_rate': item.product.gst,
            'cgst_amount': item_cgst,
            'sgst_amount': item_sgst,
            'gst_amount': item_total_gst,
            'total_with_gst': item_total_with_gst,
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

# -------------------- INVOICE GENERATION WITH GST - FIXED --------------------

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

    # Get company details from user profile - UPDATED to use new method
    company_details = store_owner.get_company_details()

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
        
        # Calculate GST amounts - FIXED: Convert to Decimal first
        gst_rate = Decimal(str(item.product.gst))  # Convert to Decimal
        gst_decimal = gst_rate / Decimal('100')    # Convert percentage to decimal
        item_total_gst = item_subtotal * gst_decimal
        item_cgst = item_total_gst / Decimal('2')  # CGST = GST/2
        item_sgst = item_total_gst / Decimal('2')  # SGST = GST/2
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
        gst_rate_float = float(gst_rate)  # For dictionary key
        if gst_rate_float not in gst_summary:
            gst_summary[gst_rate_float] = {
                'rate': gst_rate_float,
                'taxable_amount': Decimal('0.00'),
                'cgst': Decimal('0.00'),
                'sgst': Decimal('0.00'),
                'total_gst': Decimal('0.00')
            }
        
        gst_summary[gst_rate_float]['taxable_amount'] += item_subtotal
        gst_summary[gst_rate_float]['cgst'] += item_cgst
        gst_summary[gst_rate_float]['sgst'] += item_sgst
        gst_summary[gst_rate_float]['total_gst'] += item_total_gst

    # Update order with calculated totals
    order.subtotal = order_subtotal
    order.total_cgst = order_total_cgst
    order.total_sgst = order_total_sgst
    order.total_gst = order_total_cgst + order_total_sgst
    
    # Add methods to order for template compatibility
    order.get_amount_in_words = lambda: f"Rupees {int(order.total_price)} Only"
    
    # Generate invoice number if not exists
    if not hasattr(order, 'invoice_number') or not getattr(order, 'invoice_number', None):
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
    """Generate PDF invoice matching invoice_template.html exactly with proper GST calculation"""
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

    # Create response object
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    # Get company details
    company_details = store_owner.get_company_details()
    
    # Create styles matching HTML template
    styles = getSampleStyleSheet()
    
    # Custom styles matching CSS
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Normal'],
        fontSize=28,
        textColor=HexColor('#e74c3c'),  # Red color like HTML
        alignment=TA_RIGHT,
        spaceAfter=15,
        fontName='Helvetica-Bold'
    )
    
    company_name_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Normal'],
        fontSize=24,
        textColor=HexColor('#2c3e50'),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=20  # Increased space below company name
    )
    
    company_details_style = ParagraphStyle(
        'CompanyDetails',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#555555'),
        alignment=TA_LEFT,
        spaceAfter=3
    )
    
    gstin_style = ParagraphStyle(
        'GSTINStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#2c3e50'),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=10
    )
    
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontSize=14,
        textColor=HexColor('#2c3e50'),
        alignment=TA_LEFT,
        fontName='Helvetica-Bold',
        spaceAfter=10
    )
    
    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#555555'),
        alignment=TA_LEFT,
        spaceAfter=3
    )
    
    invoice_details_style = ParagraphStyle(
        'InvoiceDetails',
        parent=styles['Normal'],
        fontSize=10,
        textColor=HexColor('#555555'),
        alignment=TA_RIGHT,
        spaceAfter=3
    )
    
    # Build PDF content
    story = []
    
    # Get all order items and calculate GST summary exactly like HTML template
    invoice_items = order.items.all()
    
    # Calculate GST breakdown for each item and create summary like HTML template
    updated_items = []
    gst_summary = {}  # This will match the gst_summary from HTML template
    
    order_subtotal = Decimal('0.00')
    order_total_cgst = Decimal('0.00')
    order_total_sgst = Decimal('0.00')
    
    # Process each item exactly like the HTML template does
    for item in invoice_items:
        # Calculate item subtotal
        item_subtotal = item.item_price * item.quantity
        
        # Calculate GST amounts - EXACTLY like HTML template
        gst_rate = Decimal(str(item.product.gst))  # Convert to Decimal
        gst_decimal = gst_rate / Decimal('100')    # Convert percentage to decimal
        item_total_gst = item_subtotal * gst_decimal
        item_cgst = item_total_gst / Decimal('2')  # CGST = GST/2
        item_sgst = item_total_gst / Decimal('2')  # SGST = GST/2
        
        # Update item object with calculated values (like HTML template)
        item.subtotal = item_subtotal
        item.cgst_amount = item_cgst
        item.sgst_amount = item_sgst
        item.gst_amount = item_total_gst
        
        updated_items.append(item)
        
        # Add to order totals
        order_subtotal += item_subtotal
        order_total_cgst += item_cgst
        order_total_sgst += item_sgst
        
        # Create GST summary by rate - EXACTLY like HTML template does
        gst_rate_float = float(gst_rate)  # For dictionary key
        if gst_rate_float not in gst_summary:
            gst_summary[gst_rate_float] = {
                'rate': gst_rate_float,
                'taxable_amount': Decimal('0.00'),
                'cgst': Decimal('0.00'),
                'sgst': Decimal('0.00'),
                'total_gst': Decimal('0.00')
            }
        
        gst_summary[gst_rate_float]['taxable_amount'] += item_subtotal
        gst_summary[gst_rate_float]['cgst'] += item_cgst
        gst_summary[gst_rate_float]['sgst'] += item_sgst
        gst_summary[gst_rate_float]['total_gst'] += item_total_gst

    # Update order with calculated totals (like HTML template)
    order.subtotal = order_subtotal
    order.total_cgst = order_total_cgst
    order.total_sgst = order_total_sgst
    order.total_gst = order_total_cgst + order_total_sgst
    
    # Header section matching HTML template
    header_data = [
        [
            # Company details (left column)
            [
                Paragraph(company_details['name'], company_name_style),
                Paragraph(company_details['address'], company_details_style),
                Paragraph(f"{company_details['city']}, {company_details['state']} - {company_details['pincode']}", company_details_style),
                Paragraph(f"Phone: {company_details['phone']}", company_details_style),
                Paragraph(f"Email: {company_details['email']}", company_details_style),
                Paragraph(f"GSTIN: {company_details['gstin']}", gstin_style),
            ],
            
            # Invoice details (right column)
            [
                Paragraph("TAX INVOICE", title_style),
                Paragraph(f"<b>Invoice No:</b> {getattr(order, 'invoice_number', order.id)}", invoice_details_style),
                Paragraph(f"<b>Date:</b> {order.order_date.strftime('%d/%m/%Y')}", invoice_details_style),
                Paragraph(f"<b>Due Date:</b> {order.order_date.strftime('%d/%m/%Y')}", invoice_details_style),
            ]
        ]
    ]
    
    # Create header table
    header_table = Table(header_data, colWidths=[3.5*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ('LINEBELOW', (0, 0), (-1, -1), 2, HexColor('#333333')),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 20))
    
    # Customer Details Section matching HTML
    customer_data = [
        [
            # Bill To (left column)
            [
                Paragraph("Bill To:", section_header_style),
                Paragraph(f"<b>{order.customer.name}</b>", normal_style),
                Paragraph(f"{order.customer.address if hasattr(order.customer, 'address') and order.customer.address else order.customer.place or 'Address not provided'}", normal_style),
                Paragraph(f"<b>Phone:</b> {order.customer.phone}", normal_style),
                Paragraph(f"<b>Email:</b> {order.customer.email}" if order.customer.email else "", normal_style),
            ],
            
            # Ship To (right column)
            [
                Paragraph("Ship To:", section_header_style),
                Paragraph(f"<b>{order.customer.name}</b>", normal_style),
                Paragraph(f"{order.customer.address if hasattr(order.customer, 'address') and order.customer.address else order.customer.place or 'Address not provided'}", normal_style),
                Paragraph(f"<b>Phone:</b> {order.customer.phone}", normal_style),
            ]
        ]
    ]
    
    customer_table = Table(customer_data, colWidths=[3.25*inch, 3.25*inch])
    customer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    
    story.append(customer_table)
    story.append(Spacer(1, 20))
    
    # Invoice Items Table matching HTML template exactly
    items_data = [
        ['Sr.', 'Description', 'HSN/SAC', 'Qty', 'Unit', 'Rate (Rs)', 'Amount (Rs)', 'GST Rate', 'GST Amount (Rs)']
    ]
    
    # Add items exactly like HTML template
    for i, item in enumerate(updated_items, 1):
        # Add item row with calculated values
        items_data.append([
            str(i),
            item.product.name,
            getattr(item.product, 'hsn_code', '-') or '-',
            str(item.quantity),
            getattr(item.product, 'unit', 'Nos') or 'Nos',
            f"{item.item_price:.2f}",
            f"{item.subtotal:.2f}",
            f"{item.product.gst}%",
            f"{item.gst_amount:.2f}"
        ])
    
    # Create items table
    items_table = Table(items_data, colWidths=[0.4*inch, 2.2*inch, 0.8*inch, 0.4*inch, 0.5*inch, 0.8*inch, 0.8*inch, 0.7*inch, 0.9*inch])
    
    # Style the table matching HTML
    items_table.setStyle(TableStyle([
        # Header styling
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows styling
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # Sr. column
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),    # Description column
        ('ALIGN', (2, 1), (-1, -1), 'CENTER'), # All other columns centered
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Grid and borders
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7')),
        ('BOX', (0, 0), (-1, -1), 1, HexColor('#2c3e50')),
        
        # Alternating row colors like HTML
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')]),
        
        # Padding
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # GST Summary and Totals Section matching HTML exactly
    total_gst = order_total_cgst + order_total_sgst
    grand_total = order_subtotal + total_gst
    
    # Create GST Summary Table exactly like HTML template
    gst_summary_data = [
        ['GST Rate', 'Taxable Amount (Rs)', 'CGST (Rs)', 'SGST (Rs)', 'Total GST (Rs)']
    ]
    
    # Add GST summary rows for each rate (like HTML template)
    for gst_rate, gst_data in gst_summary.items():
        gst_summary_data.append([
            f"{gst_rate}%",
            f"{gst_data['taxable_amount']:.2f}",
            f"{gst_data['cgst']:.2f}",
            f"{gst_data['sgst']:.2f}",
            f"{gst_data['total_gst']:.2f}"
        ])
    
    # Add total row (like HTML template footer)
    gst_summary_data.append([
        'Total',
        f"{order_subtotal:.2f}",
        f"{order_total_cgst:.2f}",
        f"{order_total_sgst:.2f}",
        f"{total_gst:.2f}"
    ])
    
    # Create GST Summary and Totals layout (left side GST table, right side totals)
    summary_totals_data = [
        [
            # GST Summary (left column)
            [
                Paragraph("<b>GST Summary</b>", section_header_style),
                Spacer(1, 10),
                # GST Summary Table
                Table(gst_summary_data, colWidths=[0.6*inch, 1*inch, 0.7*inch, 0.7*inch, 0.8*inch],
                style=TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#3498db')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 1, HexColor('#bdc3c7')),
                    ('BOX', (0, 0), (-1, -1), 1, HexColor('#2980b9')),
                    ('BACKGROUND', (0, -1), (-1, -1), HexColor('#ecf0f1')),  # Total row background
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Total row bold
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
            ],
            
            # Invoice Totals (right column)
            [
                Paragraph("", section_header_style),  # Empty space
                Spacer(1, 30),
                # Totals Table matching HTML layout
                Table([
                    ['Subtotal:', f'Rs{order_subtotal:.2f}'],
                    ['CGST:', f'Rs{order_total_cgst:.2f}'],
                    ['SGST:', f'Rs{order_total_sgst:.2f}'],
                    ['Grand Total:', f'Rs{grand_total:.2f}']
                ], colWidths=[1.2*inch, 1*inch],
                style=TableStyle([
                    ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 2), 'Helvetica-Bold'),
                    ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 3), (-1, 3), 16),
                    ('TEXTCOLOR', (0, 3), (-1, 3), HexColor('#2c3e50')),
                    ('BACKGROUND', (0, 3), (-1, 3), HexColor('#f8f9fa')),
                    
                ]))
            ]
        ]
    ]
    
    summary_totals_table = Table(summary_totals_data, colWidths=[4*inch, 2.5*inch])
    summary_totals_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    
    story.append(summary_totals_table)
    story.append(Spacer(1, 20))
    
    # Amount in words (matching HTML template)
    amount_words = f"Rupees {int(grand_total)} Only"
    story.append(Paragraph(f"<b>Amount in Words:</b> {amount_words}", 
                          ParagraphStyle('AmountWords', parent=normal_style, 
                                       backColor=HexColor('#e8f4f8'), 
                                       leftIndent=10, rightIndent=10, 
                                       topPadding=10, bottomPadding=10,
                                       borderWidth=0, borderColor=HexColor('#3498db'),
                                       borderPadding=4)))
    story.append(Spacer(1, 40))
    
    # Signature section only (matching HTML - no terms)
    signature_data = [
        [
            Paragraph("", normal_style),  # Empty left column
            Paragraph(f"<b>For {company_details['name']}</b><br/><br/><br/>"
                     "____________________<br/>"
                     "Authorized Signatory", 
                     ParagraphStyle('Signature', parent=normal_style, 
                                  alignment=TA_CENTER,
                                  backColor=HexColor('#f8f9fa'),
                                  borderWidth=1, borderColor=HexColor('#bdc3c7'),
                                  leftIndent=10, rightIndent=10,
                                  topPadding=20, bottomPadding=20))
        ]
    ]
    
    signature_table = Table(signature_data, colWidths=[4*inch, 2.5*inch])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(signature_table)
    
    # Build PDF
    doc.build(story)
    
    # Return response with proper headers for download
    buffer.seek(0)
    invoice_number = getattr(order, 'invoice_number', f'INV-{order.id}')
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice_number}.pdf"'
    response['Content-Length'] = len(buffer.getvalue())
    
    return response

# Keep your existing generate_invoice function as well for backward compatibility
def generate_invoice(request, username, order_id):
    """Backward compatibility - redirect to PDF generation"""
    return generate_invoice_pdf(request, username, order_id)


@login_required
def analytics_dashboard_view(request):
    """
    Render the analytics dashboard template
    """
    return render(request, 'analytics_dashboard.html', {
        'user': request.user,
        'page_title': 'Item Analytics Dashboard'
    })
    

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
    

# Monthly Report Code

import csv
from django.http import HttpResponse

@login_required
def monthly_stock_report(request):
    """Generate monthly stock report with GST calculation instead of profit"""
    user = request.user
    current_date = timezone.now()
    
    year = int(request.GET.get('year', current_date.year))
    month = int(request.GET.get('month', current_date.month))
    
    # Get all products for the store owner
    products = Product.objects.filter(store_owner=user)
    
    # Get sales data from SalesReport or Orders
    try:
        monthly_sales_reports = SalesReport.objects.filter(
            store_owner=user,
            sale_date__year=year,
            sale_date__month=month
        )
    except:
        monthly_sales_reports = None
    
    # Calculate stock details for each product
    stock_details = []
    total_stock_value = Decimal('0.00')
    total_sales_value = Decimal('0.00')
    total_gst_collected = Decimal('0.00')
    
    for product in products:
        current_stock = product.quantity
        sold_quantity = 0
        sales_amount = Decimal('0.00')
        gst_amount = Decimal('0.00')
        
        # Try SalesReport first
        if monthly_sales_reports is not None:
            product_sales = monthly_sales_reports.filter(product=product)
            sold_quantity = product_sales.aggregate(total=Sum('quantity'))['total'] or 0
            sales_amount = product_sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
        
        # Fallback to Order data
        if not sales_amount and not sold_quantity:
            monthly_orders = Order.objects.filter(
                store_owner=user,
                order_date__year=year,
                order_date__month=month
            )
            
            for order in monthly_orders:
                order_items = order.items.filter(product=product)
                for item in order_items:
                    sold_quantity += item.quantity
                    item_subtotal = item.item_price * item.quantity
                    
                    # Calculate GST for this item
                    gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
                    item_gst = item_subtotal * gst_rate_decimal
                    item_total = item_subtotal + item_gst
                    
                    sales_amount += item_total
                    gst_amount += item_gst
        else:
            # Calculate GST from sales amount (assuming sales_amount includes GST)
            if sales_amount > 0:
                gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
                # If sales_amount includes GST, extract it
                base_amount = sales_amount / (Decimal('1') + gst_rate_decimal)
                gst_amount = sales_amount - base_amount
        
        # Calculate stock value and status
        stock_value = product.price * current_stock
        
        if current_stock == 0:
            stock_status = 'Out of Stock'
            status_class = 'danger'
        elif current_stock <= 10:
            stock_status = 'Low Stock'
            status_class = 'warning'
        else:
            stock_status = 'In Stock'
            status_class = 'success'
        
        stock_detail = {
            'product': product,
            'current_stock': current_stock,
            'sold_quantity': sold_quantity,
            'sales_amount': sales_amount,
            'gst_amount': gst_amount,
            'stock_value': stock_value,
            'stock_status': stock_status,
            'status_class': status_class,
            'category': product.category or 'Uncategorized'
        }
        
        stock_details.append(stock_detail)
        total_stock_value += stock_value
        total_sales_value += sales_amount
        total_gst_collected += gst_amount
    
    # Category summary
    category_summary = {}
    for detail in stock_details:
        category = detail['category']
        if category not in category_summary:
            category_summary[category] = {
                'total_products': 0, 'total_stock': 0, 'total_sold': 0,
                'total_sales_value': Decimal('0.00'), 'total_stock_value': Decimal('0.00'),
                'total_gst_collected': Decimal('0.00'),
                'out_of_stock_count': 0, 'low_stock_count': 0
            }
        
        category_summary[category]['total_products'] += 1
        category_summary[category]['total_stock'] += detail['current_stock']
        category_summary[category]['total_sold'] += detail['sold_quantity']
        category_summary[category]['total_sales_value'] += detail['sales_amount']
        category_summary[category]['total_stock_value'] += detail['stock_value']
        category_summary[category]['total_gst_collected'] += detail['gst_amount']
        
        if detail['stock_status'] == 'Out of Stock':
            category_summary[category]['out_of_stock_count'] += 1
        elif detail['stock_status'] == 'Low Stock':
            category_summary[category]['low_stock_count'] += 1
    
    month_name = calendar.month_name[month]
    
    # Enhanced CSV export with GST
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"monthly_stock_report_{month_name}_{year}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Monthly Stock Report', f'{month_name} {year}'])
        writer.writerow(['Store Owner:', user.company_name or user.username])
        writer.writerow(['Report Generated:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['SUMMARY'])
        writer.writerow(['Total Stock Value:', f'Rs{total_stock_value:.2f}'])
        writer.writerow(['Monthly Sales:', f'Rs{total_sales_value:.2f}'])
        writer.writerow(['Total GST Collected:', f'Rs{total_gst_collected:.2f}'])
        writer.writerow(['Total Products:', len(stock_details)])
        writer.writerow([])
        
        # Product details
        writer.writerow(['PRODUCT DETAILS'])
        writer.writerow(['Category', 'Product Name', 'Current Stock', 'Units Sold', 
                        'Unit Price (Rs)', 'Stock Value (Rs)', 'Sales Amount (Rs)', 
                        'GST Amount (Rs)', 'Status'])
        
        for detail in stock_details:
            writer.writerow([
                detail['category'], detail['product'].name, detail['current_stock'],
                detail['sold_quantity'], f"{detail['product'].price:.2f}",
                f"{detail['stock_value']:.2f}", f"{detail['sales_amount']:.2f}",
                f"{detail['gst_amount']:.2f}", detail['stock_status']
            ])
        
        return response
    
    context = {
        'stock_details': stock_details,
        'category_summary': category_summary,
        'year': year,
        'month': month,
        'month_name': month_name,
        'total_stock_value': total_stock_value,
        'total_sales_value': total_sales_value,
        'total_gst_collected': total_gst_collected,
        'report_date': f"{month_name} {year}",
        'user': user,
        'prev_month': month - 1 if month > 1 else 12,
        'prev_year': year if month > 1 else year - 1,
        'next_month': month + 1 if month < 12 else 1,
        'next_year': year if month < 12 else year + 1,
        'months': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'years': list(range(2020, current_date.year + 2)),
    }
    
    return render(request, 'monthly_stock_report.html', context)

@login_required
def yearly_stock_summary(request):
    """Generate yearly summary with GST calculation instead of profit"""
    user = request.user
    current_date = timezone.now()
    year = int(request.GET.get('year', current_date.year))
    
    monthly_data = []
    for month in range(1, 13):
        # Try SalesReport first
        try:
            month_sales = SalesReport.objects.filter(
                store_owner=user,
                sale_date__year=year,
                sale_date__month=month
            )
            total_sales = month_sales.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
            total_quantity_sold = month_sales.aggregate(qty=Sum('quantity'))['qty'] or 0
            
            # Calculate GST from sales data
            total_gst = Decimal('0.00')
            for sale in month_sales:
                if sale.product.gst > 0:
                    gst_rate = Decimal(str(sale.product.gst)) / Decimal('100')
                    base_amount = sale.total_price / (Decimal('1') + gst_rate)
                    sale_gst = sale.total_price - base_amount
                    total_gst += sale_gst
            
        except:
            # Fallback to Order data
            month_orders = Order.objects.filter(
                store_owner=user,
                order_date__year=year,
                order_date__month=month
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
            'quantity_sold': total_quantity_sold
        })
    
    yearly_sales = sum(data['total_sales'] for data in monthly_data)
    yearly_gst = sum(data['total_gst'] for data in monthly_data)
    yearly_quantity = sum(data['quantity_sold'] for data in monthly_data)
    
    # CSV export for yearly summary
    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"yearly_summary_{year}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        writer = csv.writer(response)
        writer.writerow(['Yearly Stock Summary', str(year)])
        writer.writerow(['Store Owner:', user.company_name or user.username])
        writer.writerow([])
        
        # Yearly totals
        writer.writerow(['YEARLY TOTALS'])
        writer.writerow(['Total Sales:', f'Rs{yearly_sales:.2f}'])
        writer.writerow(['Total GST Collected:', f'Rs{yearly_gst:.2f}'])
        writer.writerow(['Units Sold:', yearly_quantity])
        writer.writerow([])
        
        # Monthly breakdown
        writer.writerow(['MONTHLY BREAKDOWN'])
        writer.writerow(['Month', 'Sales (Rs)', 'GST Collected (Rs)', 'Units Sold'])
        for data in monthly_data:
            writer.writerow([data['month_name'], f"{data['total_sales']:.2f}", 
                           f"{data['total_gst']:.2f}", data['quantity_sold']])
        
        return response
    
    context = {
        'monthly_data': monthly_data,
        'year': year,
        'yearly_sales': yearly_sales,
        'yearly_gst': yearly_gst,
        'yearly_quantity': yearly_quantity,
        'user': user,
        'years': list(range(2020, current_date.year + 2)),
    }
    
    return render(request, 'yearly_stock_summary.html', context)