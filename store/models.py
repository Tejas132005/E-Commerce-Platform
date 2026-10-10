# store/models.py

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.db.models import F, Max, Q
from accounts.models import CustomUser
from django.utils import timezone


# -------------------- FINANCIAL YEAR HELPERS --------------------
# Indian financial year: 1 April -> 31 March.
# A financial year is identified by its START year, e.g. FY 2025-26 -> 2025.

FINANCIAL_YEAR_START_MONTH = 4

# Order numbers at/above this offset are "parked" (deleted invoices use
# 1000000 + id, temporary resequencing uses 2000000 + id). They are never
# real invoice numbers.
DELETED_ORDER_NUMBER_OFFSET = 1000000
RESEQUENCE_TEMP_OFFSET = 2000000


def get_financial_year(value=None):
    """
    Return the FY start year for a date/datetime.
    31-Mar-2026 -> 2025 (FY 2025-26), 01-Apr-2026 -> 2026 (FY 2026-27).
    None means today (in the project's TIME_ZONE).
    """
    if value is None:
        value = timezone.localdate()
    elif isinstance(value, datetime):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    elif isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.year if value.month >= FINANCIAL_YEAR_START_MONTH else value.year - 1


def format_financial_year(start_year):
    """2025 -> '2025-26'."""
    if start_year is None:
        return ''
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def financial_year_bounds(start_year):
    """(first_day, last_day) of a financial year."""
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def format_invoice_number(sequence):
    """Existing display format of invoice numbers: INV-01, INV-02 ..."""
    return f"INV-{sequence:02d}"


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
        # Financial-year purchase reports filter lots by owner + purchase date.
        indexes = [models.Index(fields=['store_owner', 'purchase_date'], name='store_prod_owner_pdate_idx')]

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
        # Set initial_stock on first creation
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
    order_number = models.PositiveIntegerField()  # Per-user, per-financial-year invoice sequence
    financial_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Start year of the financial year (Apr-Mar) this invoice belongs to, e.g. 2025 = FY 2025-26',
    )
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
        # Invoice numbers restart every financial year, so a number is only
        # unique within (store owner, financial year).
        unique_together = ('store_owner', 'financial_year', 'order_number')
        ordering = ['-order_date']

    # ---- financial year helpers ----

    def get_invoice_reference_date(self):
        """The date that decides the financial year: invoice date, else order date, else today."""
        if self.invoice_date:
            return self.invoice_date
        if self.order_date:
            return self.order_date
        return timezone.localdate()

    @property
    def financial_year_label(self):
        return format_financial_year(self.financial_year)

    @classmethod
    def next_invoice_sequence(cls, store_owner, financial_year):
        """
        Next invoice number for this store in this financial year (1 if none yet).
        Old invoices whose financial_year is still empty are counted by their date,
        so numbering never restarts while a repair is pending.
        """
        start, end = financial_year_bounds(financial_year)
        legacy_in_year = Q(financial_year__isnull=True) & (
            Q(invoice_date__range=(start, end)) |
            Q(invoice_date__isnull=True, order_date__date__range=(start, end))
        )
        last = cls.objects.filter(
            Q(financial_year=financial_year) | legacy_in_year,
            store_owner=store_owner,
            is_deleted=False,
            order_number__lt=DELETED_ORDER_NUMBER_OFFSET,
        ).aggregate(last=Max('order_number'))['last']
        return (last or 0) + 1

    @classmethod
    def repair_financial_years(cls, store_owner=None, dry_run=False):
        """Fill missing financial_year on old invoices and fix number clashes. See store/invoice_repair.py."""
        from .invoice_repair import repair_financial_years
        owner_id = getattr(store_owner, 'pk', store_owner)
        return repair_financial_years(cls, store_owner_id=owner_id, dry_run=dry_run)

    @classmethod
    def resequence_financial_year(cls, store_owner, financial_year):
        """
        Renumber the ACTIVE invoices of one financial year to 1..N (by order_date, id)
        and refresh their INV-XX labels. Other financial years are untouched.
        Returns the number of invoices whose number changed.
        """
        with transaction.atomic():
            cls.repair_financial_years(store_owner)
            active = cls.objects.filter(
                store_owner=store_owner,
                financial_year=financial_year,
                is_deleted=False,
            )
            ordered = list(active.order_by('order_date', 'id').values_list('id', 'order_number', 'invoice_number'))
            # Park first so intermediate states never collide on the unique constraint.
            active.update(order_number=F('id') + RESEQUENCE_TEMP_OFFSET)
            changed = 0
            for index, (pk, old_number, old_label) in enumerate(ordered, start=1):
                label = format_invoice_number(index)
                cls.objects.filter(pk=pk).update(order_number=index, invoice_number=label)
                if old_number != index or old_label != label:
                    changed += 1
            return changed

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            kwargs['update_fields'] = set(update_fields) | {'financial_year', 'order_number'}
        if not self.order_number:
            # New invoice (or restored one): number it inside its financial year.
            self.financial_year = get_financial_year(self.get_invoice_reference_date())
            with transaction.atomic():
                # Serialise numbering per store owner (row lock on PostgreSQL; SQLite locks the DB on write).
                list(CustomUser.objects.select_for_update().filter(pk=self.store_owner_id).values_list('pk', flat=True))
                # Old invoices loaded without a financial year would otherwise make numbering restart at 1.
                Order.repair_financial_years(self.store_owner_id)
                self.order_number = Order.next_invoice_sequence(self.store_owner_id, self.financial_year)
                super().save(*args, **kwargs)
            return
        if self.financial_year is None:
            self.financial_year = get_financial_year(self.get_invoice_reference_date())
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

    class Meta:
        indexes = [models.Index(fields=['return_date'], name='store_return_date_idx')]

    def __str__(self):
        return f"Return {self.returned_invoice_number} - {self.product.name}"