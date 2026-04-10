# store/analytics.py - Final Complete File
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import traceback
from decimal import Decimal
from .models import Product, SalesReport, OrderItem
from accounts.models import CustomUser


def _gst_amount_from_invoiced_total(total_with_gst, gst_percent) -> Decimal:
    """
    SalesReport.total_price is stored VAT/GST-inclusive in this project.
    Extract GST component: total - total/(1+rate).
    """
    total_with_gst = total_with_gst or Decimal('0.00')
    rate = Decimal(str(gst_percent or 0)) / Decimal('100')
    divisor = Decimal('1') + rate
    if divisor == 0:
        return Decimal('0.00')
    return total_with_gst - (total_with_gst / divisor)


def _month_sales_totals(store_owner, product, year, month):
    qs = SalesReport.objects.filter(
        store_owner=store_owner,
        product=product,
        sale_date__year=year,
        sale_date__month=month,
    )
    sold_qty = qs.aggregate(total=Sum('quantity'))['total'] or 0
    sales_total = qs.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    return int(sold_qty), sales_total


def _product_purchase_export_fields(product):
    return {
        'purchased_from': getattr(product, 'purchased_from', '') or '',
        'company_gstin': getattr(product, 'company_gstin', '') or '',
        'purchase_date': product.purchase_date.isoformat() if getattr(product, 'purchase_date', None) else '',
        'purchase_invoice_number': getattr(product, 'purchase_invoice_number', '') or '',
        'measurement_type_label': product.get_measurement_type_display(),
    }


# ============== USER-SPECIFIC ANALYTICS (NEW - Username Parameter) ==============

def get_store_owner_by_username(username):
    """Get store owner by username"""
    return get_object_or_404(CustomUser, username=username)

@login_required
@require_http_methods(["GET"])
def user_item_analytics_api(request, username):
    """
    API endpoint for user-specific item analytics
    URL: /store/user1/analytics/items/
    """
    try:
        store_owner = get_store_owner_by_username(username)
        
        # Security check: Only allow store owners to access their own analytics
        if request.user != store_owner:
            return JsonResponse({
                'status': 'error',
                'message': 'Access denied. You can only view your own analytics.'
            }, status=403)
        
        print(f"User-specific analytics request for: {store_owner.username}")
        
        products = Product.objects.filter(store_owner=store_owner)
        
        if not products.exists():
            return JsonResponse({
                'status': 'success',
                'store_owner': store_owner.username,
                'summary': {
                    'total_products': 0,
                    'total_revenue_with_gst': 0,
                    'total_gst_collected': 0,
                    'total_items_sold': 0,
                    'total_items_in_stock': 0,
                    'average_revenue_per_product': 0
                },
                'items': []
            })
        
        analytics_data = []
        
        for product in products:
            # Calculate sold quantity from SalesReport for THIS store owner only
            sales_data = SalesReport.objects.filter(
                store_owner=store_owner,
                product=product
            ).aggregate(
                total_sold=Sum('quantity'),
                total_revenue=Sum('total_price'),
                total_orders=Count('order', distinct=True)
            )
            
            total_sold = sales_data['total_sold'] or 0
            total_revenue = sales_data['total_revenue'] or Decimal('0.00')
            total_orders = sales_data['total_orders'] or 0
            
            # Get detailed order items for THIS store owner only
            order_items = OrderItem.objects.filter(
                order__store_owner=store_owner,
                product=product
            )
            
            # Calculate GST breakdown
            total_revenue_with_gst = Decimal('0.00')
            total_revenue_without_gst = Decimal('0.00')
            total_gst_amount = Decimal('0.00')
            total_cgst_amount = Decimal('0.00')
            total_sgst_amount = Decimal('0.00')
            
            for item in order_items:
                item_subtotal = item.item_price * item.quantity
                gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
                item_gst_amount = item_subtotal * gst_rate_decimal
                item_cgst = item_gst_amount / Decimal('2')
                item_sgst = item_gst_amount / Decimal('2')
                item_total_with_gst = item_subtotal + item_gst_amount
                
                total_revenue_without_gst += item_subtotal
                total_gst_amount += item_gst_amount
                total_cgst_amount += item_cgst
                total_sgst_amount += item_sgst
                total_revenue_with_gst += item_total_with_gst
            
            # Calculate stock information
            sold_quantity = total_sold
            current_stock = product.quantity
            total_stock = sold_quantity + current_stock
            
            # Get last sale date
            last_sale = SalesReport.objects.filter(
                store_owner=store_owner,
                product=product
            ).order_by('-sale_date').first()
            
            last_sale_date = None
            if last_sale:
                last_sale_date = last_sale.sale_date.isoformat()
            
            # Build item analytics
            item_data = {
                'product_id': product.id,
                'product_name': product.name,
                'category': product.category or 'Uncategorized',
                'hsn_code': product.hsn_code or 'N/A',
                'batch_number': product.batch_number or 'N/A',
                'initial_stock': int(product.initial_stock),
                'current_price': float(product.price),
                'gst_rate': float(product.gst),
                'current_stock': current_stock,
                'sold_quantity': sold_quantity,
                'total_initial_stock': total_stock,
                'stock_percentage_remaining': round(float((current_stock / total_stock) * 100), 2) if total_stock > 0 else 0,
                'total_revenue_without_gst': float(total_revenue_without_gst),
                'total_cgst_collected': float(total_cgst_amount),
                'total_sgst_collected': float(total_sgst_amount),
                'total_gst_collected': float(total_gst_amount),
                'total_revenue_with_gst': float(total_revenue_with_gst),
                'total_orders': total_orders,
                'revenue_per_unit': float(total_revenue_with_gst / sold_quantity) if sold_quantity > 0 else 0,
                'is_fast_moving': sold_quantity > (total_stock * 0.7) if total_stock > 0 else False,
                'stock_status': 'Out of Stock' if current_stock == 0 else (
                    'Low Stock' if current_stock < 10 else 'In Stock'
                ),
                'created_at': product.created_at.isoformat(),
                'last_sale_date': last_sale_date,
                **_product_purchase_export_fields(product),
            }
            
            analytics_data.append(item_data)
        
        # Sort by total revenue (descending)
        analytics_data.sort(key=lambda x: x['total_revenue_with_gst'], reverse=True)
        
        # Calculate summary statistics
        total_products = len(analytics_data)
        total_revenue_all = sum(item['total_revenue_with_gst'] for item in analytics_data)
        total_gst_all = sum(item['total_gst_collected'] for item in analytics_data)
        total_items_sold = sum(item['sold_quantity'] for item in analytics_data)
        total_items_in_stock = sum(item['current_stock'] for item in analytics_data)
        
        response_data = {
            'status': 'success',
            'store_owner': store_owner.username,
            'summary': {
                'total_products': total_products,
                'total_revenue_with_gst': round(total_revenue_all, 2),
                'total_gst_collected': round(total_gst_all, 2),
                'total_items_sold': total_items_sold,
                'total_items_in_stock': total_items_in_stock,
                'average_revenue_per_product': round(total_revenue_all / total_products, 2) if total_products > 0 else 0
            },
            'items': analytics_data
        }
        
        print(f"Returning analytics data for {store_owner.username}: {len(analytics_data)} items")
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in user_item_analytics_api: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def user_single_item_analytics_api(request, username, product_id):
    """
    API endpoint for user-specific single item analytics
    URL: /store/user1/analytics/item/123/
    """
    try:
        store_owner = get_store_owner_by_username(username)
        
        if request.user != store_owner:
            return JsonResponse({
                'status': 'error',
                'message': 'Access denied.'
            }, status=403)
        
        product = get_object_or_404(
            Product, id=product_id, store_owner=store_owner,
        )
        
        # Calculate sales data for this specific user's product
        sales_data = SalesReport.objects.filter(
            store_owner=store_owner,
            product=product
        ).aggregate(
            total_sold=Sum('quantity'),
            total_orders=Count('order', distinct=True)
        )
        
        total_sold = sales_data['total_sold'] or 0
        total_orders = sales_data['total_orders'] or 0
        
        # Get order items for GST calculations
        order_items = OrderItem.objects.filter(
            order__store_owner=store_owner,
            product=product
        )
        
        total_revenue_with_gst = Decimal('0.00')
        total_revenue_without_gst = Decimal('0.00')
        total_gst_amount = Decimal('0.00')
        total_cgst_amount = Decimal('0.00')
        total_sgst_amount = Decimal('0.00')
        
        for item in order_items:
            item_subtotal = item.item_price * item.quantity
            gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
            item_gst_amount = item_subtotal * gst_rate_decimal
            item_cgst = item_gst_amount / Decimal('2')
            item_sgst = item_gst_amount / Decimal('2')
            item_total_with_gst = item_subtotal + item_gst_amount
            
            total_revenue_without_gst += item_subtotal
            total_gst_amount += item_gst_amount
            total_cgst_amount += item_cgst
            total_sgst_amount += item_sgst
            total_revenue_with_gst += item_total_with_gst
        
        # Get recent sales
        recent_sales = SalesReport.objects.filter(
            store_owner=store_owner,
            product=product
        ).order_by('-sale_date')[:10]
        
        recent_sales_data = []
        for sale in recent_sales:
            recent_sales_data.append({
                'sale_date': sale.sale_date.isoformat(),
                'customer_name': sale.customer.name,
                'quantity': sale.quantity,
                'total_price': float(sale.total_price),
                'order_id': sale.order.id
            })
        
        current_stock = product.quantity
        total_initial_stock = total_sold + current_stock
        
        response_data = {
            'status': 'success',
            'store_owner': store_owner.username,
            'product': {
                'id': product.id,
                'name': product.name,
                'category': product.category or 'Uncategorized',
                'hsn_code': product.hsn_code or 'N/A',
                'batch_number': product.batch_number or 'N/A',
                'initial_stock': int(product.initial_stock),
                'current_price': float(product.price),
                'gst_rate': float(product.gst),
                'created_at': product.created_at.isoformat(),
            },
            'stock_analytics': {
                'current_stock': current_stock,
                'sold_quantity': total_sold,
                'total_initial_stock': total_initial_stock,
                'stock_turnover_percentage': round(float((total_sold / total_initial_stock) * 100), 2) if total_initial_stock > 0 else 0,
                'stock_status': 'Out of Stock' if current_stock == 0 else (
                    'Low Stock' if current_stock < 10 else 'In Stock'
                ),
            },
            'revenue_analytics': {
                'total_revenue_without_gst': float(total_revenue_without_gst),
                'total_cgst_collected': float(total_cgst_amount),
                'total_sgst_collected': float(total_sgst_amount),
                'total_gst_collected': float(total_gst_amount),
                'total_revenue_with_gst': float(total_revenue_with_gst),
                'revenue_per_unit_in_stock': float(total_revenue_with_gst / current_stock) if current_stock > 0 else 0
            },
            'sales_analytics': {
                'total_orders': total_orders,
                'average_quantity_per_order': round(float(total_sold / total_orders), 2) if total_orders > 0 else 0,
                'recent_sales': recent_sales_data
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def user_category_analytics_api(request, username):
    """
    API endpoint for user-specific category analytics
    URL: /store/user1/analytics/categories/
    """
    try:
        store_owner = get_store_owner_by_username(username)
        
        if request.user != store_owner:
            return JsonResponse({
                'status': 'error',
                'message': 'Access denied.'
            }, status=403)
        
        products = Product.objects.filter(store_owner=store_owner)
        
        if not products.exists():
            return JsonResponse({
                'status': 'success',
                'store_owner': store_owner.username,
                'summary': {
                    'total_categories': 0,
                    'total_revenue_all_categories': 0,
                    'total_products_all_categories': 0
                },
                'categories': []
            })
        
        category_data = {}
        
        for product in products:
            category = product.category or 'Uncategorized'
            
            if category not in category_data:
                category_data[category] = {
                    'category_name': category,
                    'total_products': 0,
                    'total_revenue_with_gst': Decimal('0.00'),
                    'total_gst_collected': Decimal('0.00'),
                    'total_sold_quantity': 0,
                    'total_current_stock': 0,
                    'products': []
                }
            
            # Calculate sales for this product for THIS store owner only
            sales_data = SalesReport.objects.filter(
                store_owner=store_owner,
                product=product
            ).aggregate(
                total_sold=Sum('quantity')
            )
            
            total_sold = sales_data['total_sold'] or 0
            
            # Calculate GST for this product for THIS store owner only
            order_items = OrderItem.objects.filter(
                order__store_owner=store_owner,
                product=product
            )
            
            product_revenue_with_gst = Decimal('0.00')
            product_gst_amount = Decimal('0.00')
            
            for item in order_items:
                item_subtotal = item.item_price * item.quantity
                gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
                item_gst_amount = item_subtotal * gst_rate_decimal
                item_total_with_gst = item_subtotal + item_gst_amount
                
                product_revenue_with_gst += item_total_with_gst
                product_gst_amount += item_gst_amount
            
            # Add to category totals
            category_data[category]['total_products'] += 1
            category_data[category]['total_revenue_with_gst'] += product_revenue_with_gst
            category_data[category]['total_gst_collected'] += product_gst_amount
            category_data[category]['total_sold_quantity'] += total_sold
            category_data[category]['total_current_stock'] += product.quantity
        
        # Convert to list and add percentages
        categories_list = []
        total_revenue_all_categories = sum(float(cat['total_revenue_with_gst']) for cat in category_data.values())
        
        for category_info in category_data.values():
            category_revenue = float(category_info['total_revenue_with_gst'])
            revenue_percentage = round((category_revenue / total_revenue_all_categories) * 100, 2) if total_revenue_all_categories > 0 else 0
            
            categories_list.append({
                'category_name': category_info['category_name'],
                'total_products': category_info['total_products'],
                'total_revenue_with_gst': category_revenue,
                'total_gst_collected': float(category_info['total_gst_collected']),
                'total_sold_quantity': category_info['total_sold_quantity'],
                'total_current_stock': category_info['total_current_stock'],
                'revenue_percentage': revenue_percentage,
                'average_revenue_per_product': round(category_revenue / category_info['total_products'], 2) if category_info['total_products'] > 0 else 0
            })
        
        categories_list.sort(key=lambda x: x['total_revenue_with_gst'], reverse=True)
        
        response_data = {
            'status': 'success',
            'store_owner': store_owner.username,
            'summary': {
                'total_categories': len(categories_list),
                'total_revenue_all_categories': round(total_revenue_all_categories, 2),
                'total_products_all_categories': sum(cat['total_products'] for cat in categories_list)
            },
            'categories': categories_list
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

# ============== GLOBAL ANALYTICS (Existing - request.user) ==============

@login_required
@require_http_methods(["GET"])
def item_analytics_api(request):
    """
    Global analytics using request.user
    URL: /store/analytics/items/
    """
    try:
        store_owner = request.user
        products = Product.objects.filter(store_owner=store_owner)
        
        if not products.exists():
            return JsonResponse({
                'status': 'success',
                'store_owner': store_owner.username,
                'summary': {
                    'total_products': 0,
                    'total_revenue_with_gst': 0,
                    'total_gst_collected': 0,
                    'total_items_sold': 0,
                    'total_items_in_stock': 0,
                    'average_revenue_per_product': 0
                },
                'items': []
            })
        
        analytics_data = []
        
        for product in products:
            sales_data = SalesReport.objects.filter(
                store_owner=store_owner,
                product=product
            ).aggregate(
                total_sold=Sum('quantity'),
                total_orders=Count('order', distinct=True)
            )
            
            total_sold = sales_data['total_sold'] or 0
            total_orders = sales_data['total_orders'] or 0
            
            order_items = OrderItem.objects.filter(
                order__store_owner=store_owner,
                product=product
            )
            
            total_revenue_with_gst = Decimal('0.00')
            total_gst_amount = Decimal('0.00')
            
            for item in order_items:
                item_subtotal = item.item_price * item.quantity
                gst_rate_decimal = Decimal(str(product.gst)) / Decimal('100')
                item_gst_amount = item_subtotal * gst_rate_decimal
                item_total_with_gst = item_subtotal + item_gst_amount
                
                total_gst_amount += item_gst_amount
                total_revenue_with_gst += item_total_with_gst
            
            current_stock = product.quantity
            total_stock = total_sold + current_stock

            item_data = {
                'product_id': product.id,
                'product_name': product.name,
                'category': product.category or 'Uncategorized',
                'hsn_code': product.hsn_code or 'N/A',
                'batch_number': product.batch_number or 'N/A',
                'initial_stock': int(product.initial_stock),
                'current_price': float(product.price),
                'gst_rate': float(product.gst),
                'current_stock': current_stock,
                'sold_quantity': total_sold,
                'total_initial_stock': total_stock,
                'total_gst_collected': float(total_gst_amount),
                'total_revenue_with_gst': float(total_revenue_with_gst),
                'total_orders': total_orders,
                'stock_status': 'Out of Stock' if current_stock == 0 else (
                    'Low Stock' if current_stock < 10 else 'In Stock'
                ),
                'is_fast_moving': total_sold > (total_stock * 0.7) if total_stock > 0 else False,
                'created_at': product.created_at.isoformat(),
                **_product_purchase_export_fields(product),
            }
            
            analytics_data.append(item_data)
        
        analytics_data.sort(key=lambda x: x['total_revenue_with_gst'], reverse=True)
        
        total_products = len(analytics_data)
        total_revenue_all = sum(item['total_revenue_with_gst'] for item in analytics_data)
        total_gst_all = sum(item['total_gst_collected'] for item in analytics_data)
        total_items_sold = sum(item['sold_quantity'] for item in analytics_data)
        total_items_in_stock = sum(item['current_stock'] for item in analytics_data)
        
        response_data = {
            'status': 'success',
            'store_owner': store_owner.username,
            'summary': {
                'total_products': total_products,
                'total_revenue_with_gst': round(total_revenue_all, 2),
                'total_gst_collected': round(total_gst_all, 2),
                'total_items_sold': total_items_sold,
                'total_items_in_stock': total_items_in_stock,
                'average_revenue_per_product': round(total_revenue_all / total_products, 2) if total_products > 0 else 0
            },
            'items': analytics_data
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def single_item_analytics_api(request, product_id):
    """Global single item analytics using request.user"""
    try:
        store_owner = request.user
        product = get_object_or_404(
            Product, id=product_id, store_owner=store_owner,
        )
        
        # Same logic as user_single_item_analytics_api but using request.user
        sales_data = SalesReport.objects.filter(
            store_owner=store_owner,
            product=product
        ).aggregate(
            total_sold=Sum('quantity'),
            total_orders=Count('order', distinct=True)
        )
        
        total_sold = sales_data['total_sold'] or 0
        total_orders = sales_data['total_orders'] or 0
        current_stock = product.quantity
        
        response_data = {
            'status': 'success',
            'product': {
                'id': product.id,
                'name': product.name,
                'category': product.category or 'Uncategorized',
                'hsn_code': product.hsn_code or 'N/A',
                'batch_number': product.batch_number or 'N/A',
                'initial_stock': int(product.initial_stock),
                'current_price': float(product.price),
                'gst_rate': float(product.gst),
            },
            'stock_analytics': {
                'current_stock': current_stock,
                'sold_quantity': total_sold,
                'stock_status': 'Out of Stock' if current_stock == 0 else (
                    'Low Stock' if current_stock < 10 else 'In Stock'
                ),
            },
            'sales_analytics': {
                'total_orders': total_orders
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def category_analytics_api(request):
    """Global category analytics using request.user"""
    try:
        store_owner = request.user
        products = Product.objects.filter(store_owner=store_owner)
        
        if not products.exists():
            return JsonResponse({
                'status': 'success',
                'store_owner': store_owner.username,
                'categories': []
            })
        
        # Same category logic as user version but using request.user
        category_data = {}
        
        for product in products:
            category = product.category or 'Uncategorized'
            if category not in category_data:
                category_data[category] = {
                    'category_name': category,
                    'total_products': 0,
                    'total_revenue_with_gst': 0,
                    'total_current_stock': 0
                }
            
            category_data[category]['total_products'] += 1
            category_data[category]['total_current_stock'] += product.quantity
        
        categories_list = list(category_data.values())
        
        response_data = {
            'status': 'success',
            'store_owner': store_owner.username,
            'categories': categories_list
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
@login_required
@require_http_methods(["GET"])
def ad_section_api(request):
    """
    Advanced Data (AD) Section API
    Includes all product fields + calculated analytics fields.
    URL: /store/analytics/ad-section/
    """
    try:
        user = request.user
        import datetime

        now = datetime.datetime.now()
        year = int(request.GET.get('year', now.year))
        month = int(request.GET.get('month', now.month))

        products = Product.objects.filter(store_owner=user)
        results = []

        for product in products:
            sold_qty, sales_amt = _month_sales_totals(user, product, year, month)
            gst_amt = _gst_amount_from_invoiced_total(sales_amt, product.gst)

            current_stock = int(product.quantity)
            initial_stock_month_start = current_stock + sold_qty
            units_sold = initial_stock_month_start - current_stock

            results.append({
                'id': product.id,
                'purchased_from': product.purchased_from or '',
                'company_gstin': product.company_gstin or '',
                'purchase_date': product.purchase_date.isoformat() if product.purchase_date else '',
                'purchase_invoice_number': product.purchase_invoice_number or '',
                'product_name': product.name,
                'category': product.category or '',
                'gst_percentage': float(product.gst),
                'hsn_code': product.hsn_code or '',
                'batch_number': product.batch_number or '',
                'quantity': product.quantity,
                'measurement_type': product.get_measurement_type_display(),
                'unit_amount': float(product.unit_amount or 0),
                'net_amount': float(product.net_amount or 0),
                'initial_stock': initial_stock_month_start,
                'current_stock': product.quantity,
                'units_sold': units_sold,
                'gst_amount': float(gst_amt),
                'is_archived': product.is_archived,
            })

        return JsonResponse({
            'status': 'success',
            'year': year,
            'month': month,
            'data': results,
        })
    except Exception as e:
        print(f"AD Section Error: {traceback.format_exc()}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
