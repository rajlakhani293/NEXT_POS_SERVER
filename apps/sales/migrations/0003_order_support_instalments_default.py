from django.db import migrations, models


def disable_empty_instalment_support(apps, schema_editor):
    Order = apps.get_model("sales", "Order")
    OrderInstalment = apps.get_model("sales", "OrderInstalment")
    order_ids_with_instalments = OrderInstalment.objects.values_list("sale_order_id", flat=True)
    Order.objects.exclude(id__in=order_ids_with_instalments).update(support_instalments=False)


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0002_alter_order_payment_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="support_instalments",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(disable_empty_instalment_support, migrations.RunPython.noop),
    ]
