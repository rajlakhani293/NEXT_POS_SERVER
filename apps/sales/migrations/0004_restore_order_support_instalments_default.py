from django.db import migrations, models


def enable_open_order_instalment_support(apps, schema_editor):
    Order = apps.get_model("sales", "Order")
    Order.objects.filter(payment_status__in=["unpaid", "partially_paid"]).update(
        support_instalments=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0003_order_support_instalments_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="support_instalments",
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_open_order_instalment_support, migrations.RunPython.noop),
    ]
