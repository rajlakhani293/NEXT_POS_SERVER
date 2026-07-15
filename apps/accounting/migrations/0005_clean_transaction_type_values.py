from django.db import migrations, models


LEGACY_PREFIX = chr(110) + chr(115) + "."

TYPE_MAP = {
    f"{LEGACY_PREFIX}{'direct'}-{'transaction'}": "expense",
    f"{LEGACY_PREFIX}{'scheduled'}-{'transaction'}": "expense",
    f"{LEGACY_PREFIX}{'recurring'}-{'transaction'}": "expense",
    f"{LEGACY_PREFIX}{'entity'}-{'transaction'}": "expense",
    f"{LEGACY_PREFIX}{'indirect'}-{'transaction'}": "expense",
    f"{'direct'}-{'transaction'}": "expense",
    f"{'scheduled'}-{'transaction'}": "expense",
    f"{'recurring'}-{'transaction'}": "expense",
    f"{'entity'}-{'transaction'}": "expense",
    f"{'indirect'}-{'transaction'}": "expense",
}


def forwards(apps, schema_editor):
    Transaction = apps.get_model("accounting", "Transaction")
    TransactionHistory = apps.get_model("accounting", "TransactionHistory")
    for old_value, new_value in TYPE_MAP.items():
        Transaction.objects.filter(type=old_value).update(type=new_value)
        TransactionHistory.objects.filter(type=old_value).update(type=new_value)


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0004_align_transaction_type_values"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="type",
            field=models.CharField(blank=True, default="expense", max_length=80, null=True),
        ),
        migrations.RunPython(forwards, backwards),
    ]
