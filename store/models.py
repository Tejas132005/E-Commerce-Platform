# store/models.py

from decimal import Decimal, InvalidOperation

from django.db import models
from accounts.models import CustomUser
from django.utils import timezone


def format_unit_value_display(value):
    """Pretty numeric for labels (strip trailing zeros)."""
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return "1"
    d = d.normalize()
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


class Product(models.Model):
    MEASUREMENT_CHOICES = [
        ('kg', 'Kilogram'),
        ('grams', 'Grams'),
        ('liter', 'Liter'),
        ('ml', 'Milliliter'),
    ]

    store_owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='products')
    purchased_from = models.CharField(
        max_length=255,
        help_text='Supplier / company name (purchased from)',
    )
    company_gstin = models.CharField(
        max_length=15,
        blank=True,
        help_text='Supplier GSTIN (optional, 15 characters)',
    )
    purchase_date = models.DateField(help_text='Date of purchase from supplier')
    purchase_invoice_number = models.CharField(
        max_length=100,
        help_text='Supplier purchase invoice number',
    )
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    initial_stock = models.PositiveIntegerField(default=0, help_text="Stock quantity at time of creation")
    category = models.CharField(max_length=100, blank=True, null=True)
    gst = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='IGST percentage')
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    batch_number = models.CharField(max_length=50, blank=True, null=True)
    measurement_type = models.CharField(max_length=10, choices=MEASUREMENT_CHOICES, default='kg')
    unit_value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('1'),
        help_text='Pack / unit size (e.g. 1 with kg → "1 kg", 500 with grams → "500 grams")',
    )
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    unit_capacity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('1.00'), help_text="Quantity per unit (e.g. 50 for 50kg bag)")
    taxable_unit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Price per unit (excl. GST)")
    taxable_total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Total taxable amount (taxable_unit_amount * quantity)")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="GST-inclusive total")
    
    # Old fields kept for compatibility for now
    unit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Price per unit (AD Section)")
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Total amount (unit_amount * quantity)")
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        pass

    UNIT_LABEL_SUFFIX = {
        'kg': 'kg',
        'grams': 'grams',
        'liter': 'ltr',
        'ml': 'ml',
    }

    def __str__(self):
        return f"{self.store_owner.username} - {self.name}"

    def get_unit_label(self):
        """Display string: '<unit_capacity> <unit>' e.g. 50 kg, 2 ltr."""
        # Use unit_capacity for new fields, fallback logic or just use capacity if provided
        val = self.unit_capacity
        if val == Decimal('1.00') and self.unit_value != Decimal('1.0000'):
            val = self.unit_value
            
        num = format_unit_value_display(val)
        suffix = self.UNIT_LABEL_SUFFIX.get(self.measurement_type, self.measurement_type or '')
        return f'{num} {suffix}'.strip()

    @property
    def uses_igst(self):
        """Return True if IGST is the applicable tax for this product."""
        return self.igst is not None and self.igst > 0

    @property
    def effective_tax_rate(self):
        """Return the effective tax rate (IGST if set, else GST)."""
        if self.uses_igst:
            return self.igst
        return self.gst

    @property
    def total_unit_amount(self):
        """Unit price inclusive of tax (GST or IGST)."""
        rate = Decimal(str(self.effective_tax_rate)) / Decimal('100')
        return (self.taxable_unit_amount * (Decimal('1') + rate)).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        # On creation, initial_stock must match the starting quantity
        if not self.pk:
            self.initial_stock = self.quantity
        super().save(*args, **kwargs)

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
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateField(
        help_text='Sale / line date chosen when adding to cart',
    )
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
    order_number = models.PositiveIntegerField()  # Per-user order numbering
    order_date = models.DateTimeField(auto_now_add=True)
    invoice_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date shown on invoice (from cart line dates at checkout)',
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # GST breakdown fields
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_cgst = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_sgst = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_gst = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_igst = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=Decimal('0.00'))
    invoice_number = models.CharField(max_length=50, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('store_owner', 'order_number')
        ordering = ['-order_date']

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Only consider non-deleted orders for the sequence
            last_order = Order.objects.filter(
                store_owner=self.store_owner,
                is_deleted=False
            ).order_by('-order_number').first()
            if last_order:
                self.order_number = last_order.order_number + 1
            else:
                self.order_number = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number} - {self.store_owner.username}"

    @property
    def display_order_id(self):
        return self.order_number

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # GST breakdown fields
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=Decimal('0.00'))

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
    sale_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Sale: {self.product.name} - {self.store_owner.username}"

class ProductReturn(models.Model):
    purchase_invoice_number = models.CharField(max_length=100)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='returns')
    returned_invoice_number = models.CharField(max_length=100)
    stock_returned = models.PositiveIntegerField()
    current_stock = models.PositiveIntegerField()
    return_date = models.DateField()
    
    taxable_unit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    gst = models.DecimalField(max_digits=5, decimal_places=2)
    igst = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    taxable_total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return {self.returned_invoice_number} - {self.product.name}"