# Generated for NexoPOS procurement table alignment.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0001_initial"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.CharField(blank=True, max_length=255, null=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
                ("name", models.CharField(max_length=255)),
                ("value", models.FloatField(default=0)),
                ("cost", models.FloatField(default=0)),
                ("tax_value", models.FloatField(default=0)),
                ("invoice_reference", models.CharField(blank=True, max_length=255, null=True)),
                ("automatic_approval", models.BooleanField(default=False, null=True)),
                ("delivery_time", models.DateTimeField(blank=True, null=True)),
                ("invoice_date", models.DateTimeField(blank=True, null=True)),
                ("payment_status", models.CharField(default="unpaid", max_length=120)),
                ("delivery_status", models.CharField(default="pending", max_length=120)),
                ("total_items", models.IntegerField(default=0)),
                ("description", models.TextField(blank=True, null=True)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
            ],
            options={
                "db_table": "procurements",
                "ordering": ["-id"],
            },
        ),
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.CharField(blank=True, max_length=255, null=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
                ("first_name", models.CharField(max_length=255)),
                ("last_name", models.CharField(blank=True, max_length=255, null=True)),
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("address_1", models.CharField(blank=True, max_length=255, null=True)),
                ("address_2", models.CharField(blank=True, max_length=255, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("amount_due", models.FloatField(default=0)),
                ("amount_paid", models.FloatField(default=0)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
            ],
            options={
                "db_table": "providers",
                "ordering": ["first_name"],
            },
        ),
        migrations.AddField(
            model_name="purchaseorder",
            name="provider",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procurements", to="purchases.supplier"),
        ),
        migrations.CreateModel(
            name="PurchaseItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.CharField(blank=True, max_length=255, null=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
                ("name", models.CharField(max_length=255)),
                ("gross_purchase_price", models.FloatField(default=0)),
                ("net_purchase_price", models.FloatField(default=0)),
                ("purchase_price", models.FloatField(default=0)),
                ("quantity", models.FloatField()),
                ("available_quantity", models.FloatField()),
                ("barcode", models.CharField(blank=True, max_length=255, null=True)),
                ("expiration_date", models.DateTimeField(blank=True, null=True)),
                ("tax_type", models.CharField(default="exclusive", max_length=120)),
                ("tax_value", models.FloatField(default=0)),
                ("total_purchase_price", models.FloatField(default=0)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
                ("convert_unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="converted_procurement_products", to="catalog.unit")),
                ("procurement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="products", to="purchases.purchaseorder")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_items", to="catalog.product")),
                ("tax_group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="procurement_products", to="catalog.taxgroup")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="procurement_products", to="catalog.unit")),
            ],
            options={
                "db_table": "procurements_products",
            },
        ),
    ]
