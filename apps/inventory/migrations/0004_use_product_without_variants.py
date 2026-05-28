# Generated manually for simplified product inventory.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_simplify_product_branch_fields"),
        ("inventory", "0003_alter_lowstockalert_status_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="stocklot",
            old_name="variant",
            new_name="product",
        ),
        migrations.AlterField(
            model_name="stocklot",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stock_lots",
                to="catalog.product",
            ),
        ),
        migrations.RenameField(
            model_name="stockledger",
            old_name="variant",
            new_name="product",
        ),
        migrations.AlterField(
            model_name="stockledger",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stock_entries",
                to="catalog.product",
            ),
        ),
        migrations.RenameField(
            model_name="stocktransferitem",
            old_name="variant",
            new_name="product",
        ),
        migrations.AlterField(
            model_name="stocktransferitem",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="transfer_items",
                to="catalog.product",
            ),
        ),
        migrations.RemoveField(
            model_name="lowstockalert",
            name="variant",
        ),
    ]
