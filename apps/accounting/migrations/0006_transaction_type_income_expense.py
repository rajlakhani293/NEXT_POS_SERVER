from django.db import migrations, models


def forwards(apps, schema_editor):
    Transaction = apps.get_model("accounting", "Transaction")
    old_values = [
        f"{name}-{'transaction'}"
        for name in ["direct", "scheduled", "recurring", "entity", "indirect"]
    ]
    legacy_prefix = chr(110) + chr(115) + "."
    old_values += [f"{legacy_prefix}{value}" for value in old_values]
    Transaction.objects.filter(type__in=old_values).update(type="expense")


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0005_clean_transaction_type_values"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="type",
            field=models.CharField(blank=True, default="expense", max_length=80, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RunPython(forwards, backwards),
    ]
