# Generated manually for simplified products without variants.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_simplify_product_branch_fields"),
        ("inventory", "0004_use_product_without_variants"),
        ("purchases", "0003_remove_purchaseitem_variant"),
        ("sales", "0003_remove_saleitem_variant"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ProductBarcode",
        ),
        migrations.DeleteModel(
            name="ProductVariantBranch",
        ),
        migrations.DeleteModel(
            name="ProductVariant",
        ),
    ]
