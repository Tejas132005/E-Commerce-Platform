# Step 1/3 of financial-year invoice numbering: add the (nullable) column.
# Purely additive - no existing row is changed.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0018_order_total_igst_orderitem_igst_amount_product_igst_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='financial_year',
            field=models.PositiveSmallIntegerField(
                blank=True,
                db_index=True,
                help_text='Start year of the financial year (Apr-Mar) this invoice belongs to, e.g. 2025 = FY 2025-26',
                null=True,
            ),
        ),
    ]
