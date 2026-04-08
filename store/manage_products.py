# store/manage_products.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Product
from .forms import AddProductForm, UpdateProductForm


@login_required
def add_new_product(request):
    """Add a new product to the logged-in user's store."""
    ad_section = (
        (request.GET.get('ad') == 'true')
        if request.method != 'POST'
        else (request.POST.get('ad_section') == '1')
    )
    if request.method == 'POST':
        form = AddProductForm(
            request.POST,
            request.FILES,
            store_owner=request.user,
            ad_section=ad_section,
        )
        if form.is_valid():
            product = form.save(commit=False)
            product.store_owner = request.user
            product.price = 0
            product.save()
            messages.success(request, f'Product "{product.name}" added successfully!')
            next_url = 'add_product'
            if ad_section:
                from django.urls import reverse
                next_url = f"{reverse('add_product')}?ad=true"
            return redirect(next_url)
    else:
        form = AddProductForm(store_owner=request.user, ad_section=ad_section)

    return render(request, 'add_product.html', {'form': form, 'ad_section': ad_section})


@login_required
def update_existing_product(request, product_id=None):
    """Update an existing product in the logged-in user's store."""
    product = None
    ad_section = (
        (request.GET.get('ad') == 'true')
        if request.method != 'POST'
        else (request.POST.get('ad_section') == '1')
    )
    if product_id:
        # Allow editing archived SKUs when opened by direct id (e.g. AD Section link)
        product = get_object_or_404(Product, id=product_id, store_owner=request.user)

    if request.method == 'POST':
        pid = product_id or request.POST.get('product_id')
        if not pid:
            messages.error(request, 'No product selected.')
            return redirect('update_product')
        product = get_object_or_404(Product, id=pid, store_owner=request.user)
        form = UpdateProductForm(
            request.POST,
            request.FILES,
            instance=product,
            store_owner=request.user,
            ad_section=ad_section,
        )
        if form.is_valid():
            form.save()
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('product_list')
    elif product:
        form = UpdateProductForm(
            instance=product,
            store_owner=request.user,
            ad_section=ad_section,
        )
    else:
        form = None

    user_products = Product.objects.filter(store_owner=request.user, is_archived=False).order_by('category', 'name')
    return render(request, 'update_product.html', {
        'products': user_products,
        'product': product,
        'form': form,
        'ad_section': ad_section,
    })


@login_required
def delete_product(request, product_id=None):
    """Delete a product from the logged-in user's store."""
    if request.method == 'POST':
        pid = product_id or request.POST.get('product_id')
        if pid:
            try:
                product = Product.objects.get(id=pid, store_owner=request.user)
                product_name = product.name
                product.delete()
                messages.success(request, f'Product "{product_name}" deleted successfully!')
            except Product.DoesNotExist:
                messages.error(request, 'Product not found in your store.')
        else:
            messages.error(request, 'No product selected for deletion.')

        return redirect('product_list')

    user_products = Product.objects.filter(store_owner=request.user, is_archived=False).order_by('category', 'name')
    return render(request, 'delete_product.html', {'products': user_products})


@login_required
def product_list_view(request):
    """View all active products for the logged-in store owner."""
    from django.db.models import Sum
    from decimal import Decimal
    from .models import SalesReport

    products = Product.objects.filter(store_owner=request.user, is_archived=False).order_by('category', 'name')
    low_stock_count = products.filter(quantity__gt=0, quantity__lte=10).count()
    total_units = products.aggregate(s=Sum('quantity'))['s'] or 0
    category_count = products.values('category').distinct().count()
    total_revenue = SalesReport.objects.filter(store_owner=request.user).aggregate(
        t=Sum('total_price'),
    )['t'] or Decimal('0.00')

    return render(request, 'product_list.html', {
        'products': products,
        'low_stock_count': low_stock_count,
        'total_units': total_units,
        'category_count': category_count,
        'total_revenue': total_revenue,
    })


@login_required
def product_manage_detail(request, product_id):
    """Read-only full product record for store owner."""
    product = get_object_or_404(Product, id=product_id, store_owner=request.user)
    return render(request, 'product_manage_detail.html', {'product': product})


@login_required
def archive_product(request, product_id):
    """Archive a product (stock must be 0)."""
    product = get_object_or_404(Product, id=product_id, store_owner=request.user)

    if product.quantity != 0:
        messages.error(request, f'Cannot archive "{product.name}". Stock must be 0.')
        return redirect('product_list')

    product.is_archived = True
    product.save()
    messages.success(request, f'Product "{product.name}" has been archived.')
    return redirect('product_list')


@login_required
def unarchive_product(request, product_id):
    """Unarchive a product."""
    product = get_object_or_404(Product, id=product_id, store_owner=request.user)
    product.is_archived = False
    product.save()
    messages.success(request, f'Product "{product.name}" has been restored from archive.')
    return redirect('archived_products')


@login_required
def archived_products_view(request):
    """View all archived products."""
    products = Product.objects.filter(store_owner=request.user, is_archived=True).order_by('category', 'name')
    return render(request, 'archived_products.html', {'products': products})
