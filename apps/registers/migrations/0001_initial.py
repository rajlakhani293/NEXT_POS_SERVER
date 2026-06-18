# Generated for NexoPOS register table alignment.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CashRegister",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
                ("name", models.CharField(max_length=150)),
                ("code", models.SlugField(blank=True, max_length=120, null=True)),
                ("location", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True, null=True)),
                ("balance", models.DecimalField(decimal_places=5, default=0, max_digits=18)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
                ("used_by", models.ForeignKey(blank=True, db_column="used_by", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="used_registers", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "registers",
                "ordering": ["name"],
                "unique_together": {("branch", "code")},
            },
        ),
        migrations.CreateModel(
            name="CashRegisterEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
                ("payment_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("payment_type_id", models.PositiveIntegerField(default=0)),
                ("order_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("payment_type", models.CharField(blank=True, default="", max_length=80)),
                ("entry_type", models.CharField(choices=[("opening", "Opening"), ("sale_payment", "Sale Payment"), ("change_given", "Change Given"), ("refund", "Refund"), ("cash_in", "Cash In"), ("cash_out", "Cash Out"), ("expense", "Expense"), ("closing", "Closing")], db_column="action", max_length=20)),
                ("amount", models.DecimalField(db_column="value", decimal_places=5, max_digits=18)),
                ("balance_before", models.DecimalField(decimal_places=5, default=0, max_digits=18)),
                ("balance_after", models.DecimalField(decimal_places=5, default=0, max_digits=18)),
                ("transaction_type", models.CharField(blank=True, max_length=20, null=True)),
                ("reference_type", models.CharField(blank=True, max_length=50)),
                ("reference_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("note", models.TextField(blank=True, db_column="description")),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("cashier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="register_entries", to=settings.AUTH_USER_MODEL)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
                ("register", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="registers.cashregister")),
            ],
            options={
                "db_table": "registers_history",
            },
        ),
    ]
