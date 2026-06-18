from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0006_alter_transactionaccount_options_and_more"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="transactionhistory",
            table="transactions_histories",
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="is_reflection",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="reflection_source_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="order_payment_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="transaction_status",
            field=models.CharField(db_column="transaction_status", default="pending", max_length=30),
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="name",
            field=models.CharField(max_length=180),
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="transaction_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="histories",
                to="accounting.transactionaccount",
            ),
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="value",
            field=models.DecimalField(decimal_places=5, default=0, max_digits=18),
        ),
    ]
