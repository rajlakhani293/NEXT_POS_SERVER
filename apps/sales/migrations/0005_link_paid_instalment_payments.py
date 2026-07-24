from django.db import migrations


def link_paid_instalments_to_payments(apps, schema_editor):
    OrderInstalment = apps.get_model("sales", "OrderInstalment")
    OrderPayment = apps.get_model("sales", "OrderPayment")

    instalments = OrderInstalment.objects.filter(paid=True, payment_id__isnull=True).order_by(
        "sale_order_id",
        "id",
    )
    used_payment_ids = set()
    for instalment in instalments:
        payment = (
            OrderPayment.objects.filter(
                sale_order_id=instalment.sale_order_id,
                value=instalment.amount,
            )
            .exclude(id__in=used_payment_ids)
            .order_by("id")
            .first()
        )
        if payment is None:
            continue
        instalment.payment_id = payment.id
        instalment.save(update_fields=["payment_id"])
        used_payment_ids.add(payment.id)


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0004_restore_order_support_instalments_default"),
    ]

    operations = [
        migrations.RunPython(link_paid_instalments_to_payments, migrations.RunPython.noop),
    ]
