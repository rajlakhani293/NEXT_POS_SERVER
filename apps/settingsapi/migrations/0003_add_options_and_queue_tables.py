from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("settingsapi", "0002_businesssetting_allow_decimal_quantities_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="FailedJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("connection", models.TextField()),
                ("queue", models.TextField()),
                ("payload", models.TextField()),
                ("exception", models.TextField()),
                ("failed_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "failed_jobs",
            },
        ),
        migrations.CreateModel(
            name="Job",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("queue", models.CharField(db_index=True, max_length=255)),
                ("payload", models.TextField()),
                ("attempts", models.PositiveSmallIntegerField()),
                ("reserved_at", models.PositiveIntegerField(blank=True, null=True)),
                ("available_at", models.PositiveIntegerField()),
                ("created_at", models.PositiveIntegerField()),
            ],
            options={
                "db_table": "jobs",
            },
        ),
        migrations.CreateModel(
            name="Option",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("key", models.CharField(max_length=255)),
                ("value", models.TextField(blank=True, null=True)),
                ("expire_on", models.DateTimeField(blank=True, null=True)),
                ("array", models.BooleanField(default=False)),
                ("user", models.ForeignKey(blank=True, db_column="user_id", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="options", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "options",
                "ordering": ["key", "id"],
            },
        ),
    ]
