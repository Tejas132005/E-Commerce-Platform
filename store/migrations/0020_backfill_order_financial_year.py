# Step 2/3: fill financial_year for EXISTING invoices.
#
# Only the new financial_year column is written. order_number, invoice_number,
# dates, totals, items, stock, customers etc. are NOT modified, so every invoice
# keeps the number it was issued with.
#
# FY rule (India): 1 April -> 31 March. Based on invoice_date (the date printed on
# the invoice); falls back to order_date in the project TIME_ZONE.

from django.db import migrations
from django.utils import timezone


def _fy(d):
    return d.year if d.month >= 4 else d.year - 1


def backfill(apps, schema_editor):
    Order = apps.get_model('store', 'Order')
    qs = Order.objects.filter(financial_year__isnull=True).only('id', 'invoice_date', 'order_date')
    for order in qs.iterator(chunk_size=500):
        if order.invoice_date:
            ref = order.invoice_date
        elif order.order_date:
            ref = timezone.localtime(order.order_date).date() if timezone.is_aware(order.order_date) else order.order_date.date()
        else:
            ref = timezone.localdate()
        Order.objects.filter(pk=order.pk).update(financial_year=_fy(ref))


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0019_order_financial_year'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
