# store/manage_products.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from .models import Product
from .forms import AddProductForm

@login_required
def add_new_product(request):
    """Add a new product to the logged-in user's store"""
    if request.method == 'POST':
        form = AddProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store_owner = request.user
            
            # Check if product already exists for this store owner
            if Product.objects.filter(
                store_owner=request.user, 
                name__iexact=product.name
            ).exists():
                messages.error(request, 'Product with this name already exists in your store.')
                return render(request, 'add_product.html', {'form': form})
            
            product.save()
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('add_product')
    else:
        form = AddProductForm()

    return render(request, 'add_product.html', {'form': form})

@login_required
def update_existing_product(request):
    """Update an existing product in the logged-in user's store"""
    if request.method == 'POST':
        product_name = request.POST.get('product_name')
        
        try:
            product = Product.objects.get(
                store_owner=request.user,
                name__iexact=product_name
            )
        except Product.DoesNotExist:
            messages.error(request, f'Product "{product_name}" not found in your store.')
            return render(request, 'update_product.html')

        # Update product fields
        product.price = request.POST.get('price', product.price)
        product.quantity = request.POST.get('quantity', product.quantity)
        product.category = request.POST.get('category', product.category)
        product.gst = request.POST.get('gst', product.gst)
        product.hsn_code = request.POST.get('hsn_code', product.hsn_code)
        
        product.save()
        messages.success(request, f'Product "{product.name}" updated successfully!')
        return redirect('update_product')

    # GET request - show user's products
    user_products = Product.objects.filter(store_owner=request.user)
    return render(request, 'update_product.html', {'products': user_products})

@login_required
def delete_product(request):
    """Delete a product from the logged-in user's store"""
    if request.method == 'POST':
        product_name = request.POST.get('product_name')
        
        try:
            product = Product.objects.get(
                store_owner=request.user,
                name__iexact=product_name
            )
            product_name_display = product.name
            product.delete()
            messages.success(request, f'Product "{product_name_display}" deleted successfully!')
        except Product.DoesNotExist:
            messages.error(request, f'Product "{product_name}" not found in your store.')
        
        return redirect('delete_product')

    # GET request - show user's products
    user_products = Product.objects.filter(store_owner=request.user)
    return render(request, 'delete_product.html', {'products': user_products})

@login_required
def product_list_view(request):
    """View all products for the logged-in store owner"""
    products = Product.objects.filter(store_owner=request.user).order_by('category', 'name')
    return render(request, 'product_list.html', {'products': products})