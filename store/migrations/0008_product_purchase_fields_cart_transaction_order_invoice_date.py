import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0007_alter_product_unit_value"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="purchased_from",
            field=models.CharField(
                default="Not specified",
                help_text="Supplier / company name (purchased from)",
                max_length=255,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="product",
            name="company_gstin",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Supplier GSTIN (optional, 15 characters)",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="purchase_date",
            field=models.DateField(
                default=datetime.date(2020, 1, 1),
                help_text="Date of purchase from supplier",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="product",
            name="purchase_invoice_number",
            field=models.CharField(
                default="N/A",
                help_text="Supplier purchase invoice number",
                max_length=100,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="cart",
            name="transaction_date",
            field=models.DateField(
                default=datetime.date.today,
                help_text="Sale / line date chosen when adding to cart",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="order",
            name="invoice_date",
            field=models.DateField(
                blank=True,
                help_text="Date shown on invoice (from cart line dates at checkout)",
                null=True,
            ),
        ),
    ]
