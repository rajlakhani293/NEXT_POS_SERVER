# Generated manually for simplified product purchases.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_simplify_product_branch_fields"),
        ("purchases", "0002_alter_purchaseitem_status_alter_purchaseorder_status_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="purchaseitem",
            name="variant",
        ),
    ]
