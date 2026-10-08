# Repairs invoices that reached this schema without a financial year (see
# store/invoice_repair.py). Old invoice numbers are kept; only invoices created
# after the upgrade that clash with an old number are moved after it.
# Safe to run on any database: does nothing when every invoice already has its year.

from django.db import migrations


def repair(apps, schema_editor):
    from store.invoice_repair import repair_financial_years
    repair_financial_years(apps.get_model('store', 'Order'))


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0022_sync_salesreport_sale_date_state'),
    ]

    operations = [
        migrations.RunPython(repair, migrations.RunPython.noop),
    ]
