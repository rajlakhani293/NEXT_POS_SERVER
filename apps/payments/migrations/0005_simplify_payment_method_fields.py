from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_paymentmethod_payment_type_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="paymentmethod",
            name="author",
        ),
        migrations.RemoveField(
            model_name="paymentmethod",
            name="method_type",
        ),
        migrations.RemoveField(
            model_name="paymentmethod",
            name="is_cash",
        ),
        migrations.RemoveField(
            model_name="paymentmethod",
            name="requires_reference",
        ),
    ]
