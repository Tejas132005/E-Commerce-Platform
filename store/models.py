# store/models.py 

from django.db import models
from accounts.models import CustomUser

class Product(models.Model):
    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=100, blank=True, null=True)
    gst = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store_owner', 'name')

    def __str__(self):
        return f"{self.store_owner.username} - {self.name}"

class ShopCustomer(models.Model):
    """Customers of individual stores"""
    phone = models.CharField(max_length=15)
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    place = models.CharField(max_length=100, blank=True, null=True)
    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='shop_customers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store_owner', 'phone')

    def __str__(self):
        return f"{self.name} - {self.store_owner.username}'s store"

class Cart(models.Model):
    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='carts')
    customer = models.ForeignKey(ShopCustomer, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('store_owner', 'customer', 'product')

    def __str__(self):
        return f"{self.customer.name} - {self.product.name}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    customer = models.ForeignKey(ShopCustomer, on_delete=models.CASCADE)
    order_date = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Order #{self.id} - {self.store_owner.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

class SalesReport(models.Model):
    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(ShopCustomer, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    profit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    category = models.CharField(max_length=100, blank=True, null=True)
    sale_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sale: {self.product.name} - {self.store_owner.username}"
    
    

