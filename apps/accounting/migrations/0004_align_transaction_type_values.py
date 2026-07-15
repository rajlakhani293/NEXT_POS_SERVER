from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0003_alter_transactionaccount_unique_together"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="type",
            field=models.CharField(blank=True, default="expense", max_length=80, null=True),
        ),
    ]
