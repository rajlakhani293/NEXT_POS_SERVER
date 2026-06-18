from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("registers", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="registershistory",
            name="cashier",
        ),
        migrations.RemoveField(
            model_name="registershistory",
            name="payment_type",
        ),
        migrations.RemoveField(
            model_name="registershistory",
            name="reference_id",
        ),
        migrations.RemoveField(
            model_name="registershistory",
            name="reference_type",
        ),
        migrations.AlterField(
            model_name="registershistory",
            name="entry_type",
            field=models.CharField(
                choices=[
                    ("register-opening", "Register Opening"),
                    ("register-closing", "Register Closing"),
                    ("register-cash-in", "Cash In"),
                    ("register-cash-out", "Cash Out"),
                    ("register-cash-delete", "Cash Delete"),
                    ("register-order-payment", "Order Payment"),
                    ("register-order-change", "Order Change"),
                    ("register-order-voucher", "Order Voucher"),
                    ("register-refund", "Refund"),
                    ("register-account-pay", "Account Pay"),
                    ("register-account-in", "Account In"),
                ],
                db_column="action",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="registershistory",
            name="note",
            field=models.TextField(blank=True, db_column="description", null=True),
        ),
    ]
