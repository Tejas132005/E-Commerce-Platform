# Step 3/3: invoice numbers are unique per (store owner, financial year).
# Existing data already satisfies this (the old constraint was stricter).

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('store', '0020_backfill_order_financial_year'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='order',
            unique_together={('store_owner', 'financial_year', 'order_number')},
        ),
    ]
