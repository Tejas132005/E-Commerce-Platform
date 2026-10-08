# core/dashboard.py
#
# Real data for the home-page charts. Read-only: nothing here writes to the DB.
# Uses the same rules as the existing Sales Dashboard: deleted invoices are excluded.

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, Max, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from store.models import (
    Order, SalesReport, ShopCustomer, financial_year_bounds, format_financial_year, get_financial_year,
)

RANGE_CHOICES = {
    '7': ('Last 7 days', 7),
    '30': ('Last 30 days', 30),
    '90': ('Last 90 days', 90),
    'fy': ('This financial year', None),
}
DEFAULT_RANGE = '30'
PAST_FY_COUNT = 10          # how many previous financial years the home page offers
TOP_ITEMS = 10
ZERO = Decimal('0.00')


def past_financial_years(today=None, count=PAST_FY_COUNT):
    """[('fy2025', 'FY 2025-26'), ...] for the `count` financial years before the current one, newest first."""
    current = get_financial_year(today or timezone.localdate())
    return [(f'fy{y}', f'FY {format_financial_year(y)}') for y in range(current - 1, current - 1 - count, -1)]


def resolve_range(key, today=None):
    """
    Return (key, label, start_date, end_date) for a range key.
    Keys: '7', '30', '90', 'fy' (current FY to date) or 'fy<start year>' for one of the
    previous PAST_FY_COUNT financial years (full 1 April - 31 March). Unknown keys fall back to 30 days.
    """
    today = today or timezone.localdate()
    if key in RANGE_CHOICES:
        label, days = RANGE_CHOICES[key]
        if days is None:
            start = financial_year_bounds(get_financial_year(today))[0]
        else:
            start = today - timedelta(days=days - 1)
        return key, label, start, today
    past = dict(past_financial_years(today))
    if key in past:
        start, end = financial_year_bounds(int(key[2:]))
        return key, past[key], start, end
    return resolve_range(DEFAULT_RANGE, today)


def _day_labels(start, end):
    days, d = [], start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def build_home_dashboard(user, range_key=DEFAULT_RANGE, today=None):
    key, label, start, end = resolve_range(range_key, today)
    tz = timezone.get_current_timezone()
    days = _day_labels(start, end)
    dec = DecimalField(max_digits=14, decimal_places=2)

    sales = SalesReport.objects.filter(store_owner=user, order__is_deleted=False).annotate(
        day=TruncDate('sale_date', tzinfo=tz)
    ).filter(day__gte=start, day__lte=end)

    # 1. days vs quantity sold
    qty_by_day = {row['day']: row['qty'] for row in sales.values('day').annotate(qty=Sum('quantity'))}
    quantity_series = [int(qty_by_day.get(d, 0) or 0) for d in days]

    # 2. items sold vs sold amount (top items by amount)
    items = list(
        sales.values('product__name')
        .annotate(qty=Sum('quantity'), amount=Coalesce(Sum('total_price'), Value(ZERO), output_field=dec))
        .order_by('-amount', 'product__name')[:TOP_ITEMS]
    )
    total_amount = sales.aggregate(t=Coalesce(Sum('total_price'), Value(ZERO), output_field=dec))['t']

    # 3. days vs invoices (by invoice date, falling back to order date for old rows)
    invoices = Order.objects.filter(store_owner=user, is_deleted=False).annotate(
        day=Coalesce('invoice_date', TruncDate('order_date', tzinfo=tz))
    ).filter(day__gte=start, day__lte=end)
    inv_by_day = {row['day']: row['n'] for row in invoices.values('day').annotate(n=Count('id'))}
    invoice_series = [inv_by_day.get(d, 0) for d in days]

    customer_count = ShopCustomer.objects.filter(store_owner=user).count()

    # Cheap fingerprint so the page only redraws when something actually changed.
    owner_orders = Order.objects.filter(store_owner=user).aggregate(n=Count('id'), last=Max('id'))
    owner_sales = SalesReport.objects.filter(store_owner=user).aggregate(n=Count('id'), last=Max('id'))
    deleted = Order.objects.filter(store_owner=user, is_deleted=True).count()
    version = f"{owner_orders['n']}-{owner_orders['last']}-{owner_sales['n']}-{owner_sales['last']}-{deleted}-{customer_count}-{start}-{end}"

    return {
        'range': {'key': key, 'label': label, 'start': start.isoformat(), 'end': end.isoformat(),
                  'is_past_fy': key not in RANGE_CHOICES},
        'days': [d.isoformat() for d in days],
        'quantity_sold': quantity_series,
        'invoices': invoice_series,
        'items': {
            'names': [row['product__name'] for row in items],
            'quantity': [int(row['qty'] or 0) for row in items],
            'amount': [float(row['amount']) for row in items],
        },
        'totals': {
            'quantity_sold': sum(quantity_series),
            'invoices': sum(invoice_series),
            'sold_amount': float(total_amount),
        },
        'customer_count': customer_count,
        'version': version,
        'generated_at': timezone.localtime().strftime('%d %b %Y, %I:%M %p'),
    }
