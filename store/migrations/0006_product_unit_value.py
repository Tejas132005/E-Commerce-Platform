# Generated manually for unit_value field

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0005_cart_unit_price_product_batch_number_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="unit_value",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("1"),
                help_text="Base pack size (e.g. 1 for 1 kg, 500 for 500 grams)",
                max_digits=12,
            ),
        ),
    ]
