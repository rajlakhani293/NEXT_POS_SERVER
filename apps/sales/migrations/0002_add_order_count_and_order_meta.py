from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("organizations", "0001_initial"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderCount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("count", models.IntegerField()),
                ("date", models.DateTimeField()),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "orders_count",
                "ordering": ["-date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="OrderMeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("key", models.CharField(max_length=255)),
                ("value", models.CharField(max_length=255)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="%(class)ss", to="organizations.company")),
                ("sale_order", models.ForeignKey(db_column="order_id", on_delete=django.db.models.deletion.CASCADE, related_name="metas", to="sales.order")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_%(app_label)s_%(class)ss", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "orders_metas",
            },
        ),
    ]
