# Generated manually for simplified product sales.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0006_simplify_product_branch_fields"),
        ("sales", "0002_alter_cartdraft_status_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="saleitem",
            name="variant",
        ),
    ]
