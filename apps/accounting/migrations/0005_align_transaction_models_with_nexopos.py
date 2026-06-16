# Generated manually to preserve accounting data while aligning field names with NexoPOS.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_nexopos_transaction_history(apps, schema_editor):
    TransactionHistory = apps.get_model("accounting", "TransactionHistory")
    for history in TransactionHistory.objects.all().iterator():
        updates = []
        if not history.name:
            history.name = getattr(history, "note", "") or ""
            updates.append("name")
        if not history.type:
            history.type = getattr(history, "source_type", "") or ""
            updates.append("type")
        if not history.trigger_date:
            transaction = getattr(history, "transaction", None)
            history.trigger_date = getattr(transaction, "scheduled_date", None) or getattr(history, "created_at", None)
            updates.append("trigger_date")
        if updates:
            history.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0004_delete_accountingsetting"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="transaction",
            old_name="created_by",
            new_name="author",
        ),
        migrations.RenameField(
            model_name="transaction",
            old_name="is_recurring",
            new_name="recurring",
        ),
        migrations.RenameField(
            model_name="transaction",
            old_name="next_run_at",
            new_name="scheduled_date",
        ),
        migrations.RenameField(
            model_name="transaction",
            old_name="recurring_rule",
            new_name="occurrence",
        ),
        migrations.AddField(
            model_name="transaction",
            name="active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="group_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="media_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="occurrence_value",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="transaction",
            name="type",
            field=models.CharField(default="ns.direct-transaction", max_length=80),
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="event_key",
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="group_code",
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="reference_number",
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="source_id",
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="source_type",
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="transaction_date",
        ),
        migrations.RemoveField(
            model_name="transaction",
            name="transaction_type",
        ),
        migrations.AlterField(
            model_name="transaction",
            name="author",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="authored_transactions", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterModelOptions(
            name="transaction",
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.RenameField(
            model_name="transactionhistory",
            old_name="account",
            new_name="transaction_account",
        ),
        migrations.RenameField(
            model_name="transactionhistory",
            old_name="action_type",
            new_name="operation",
        ),
        migrations.RenameField(
            model_name="transactionhistory",
            old_name="amount",
            new_name="value",
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="value",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="author",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="authored_transaction_histories", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="customer_account_history_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="name",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="order_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="order_product_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="order_refund_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="order_refund_product_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="procurement_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="register_history_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="trigger_date",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transactionhistory",
            name="type",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.RunPython(backfill_nexopos_transaction_history, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="transactionhistory",
            name="balance_after",
        ),
        migrations.RemoveField(
            model_name="transactionhistory",
            name="balance_before",
        ),
        migrations.RemoveField(
            model_name="transactionhistory",
            name="note",
        ),
        migrations.RemoveField(
            model_name="transactionhistory",
            name="source_id",
        ),
        migrations.RemoveField(
            model_name="transactionhistory",
            name="source_type",
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="operation",
            field=models.CharField(choices=[("debit", "Debit"), ("credit", "Credit")], default="debit", max_length=10),
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="transaction",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="histories", to="accounting.transaction"),
        ),
        migrations.AlterField(
            model_name="transactionhistory",
            name="transaction_account",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="histories", to="accounting.transactionaccount"),
        ),
        migrations.RenameField(
            model_name="transactionactionrule",
            old_name="event_key",
            new_name="on",
        ),
        migrations.RenameField(
            model_name="transactionactionrule",
            old_name="is_locked",
            new_name="locked",
        ),
        migrations.RenameField(
            model_name="transactionactionrule",
            old_name="offset_action",
            new_name="do",
        ),
        migrations.RemoveField(
            model_name="transactionactionrule",
            name="is_system",
        ),
        migrations.RemoveField(
            model_name="transactionactionrule",
            name="sort_order",
        ),
        migrations.AlterField(
            model_name="transactionactionrule",
            name="do",
            field=models.CharField(choices=[("increase", "Increase"), ("decrease", "Decrease")], default="increase", max_length=20),
        ),
        migrations.AlterField(
            model_name="transactionactionrule",
            name="on",
            field=models.CharField(default="", max_length=80),
        ),
        migrations.AlterModelOptions(
            name="transactionactionrule",
            options={"ordering": ["id"]},
        ),
        migrations.DeleteModel(
            name="ActiveTransactionHistory",
        ),
    ]
