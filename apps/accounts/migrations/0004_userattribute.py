# Generated for source profile attribute parity.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_user_options_alter_accesstoken_table_and_more"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserAttribute",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.IntegerField(choices=[(0, "Active"), (1, "Deactive"), (2, "Delete")], default=0, help_text="0: Active, 1: Inactive, 2: Deleted. Higher values are reserved for model-specific lifecycle states.")),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("avatar_link", models.CharField(blank=True, max_length=255)),
                ("theme", models.CharField(blank=True, max_length=255)),
                ("language", models.CharField(blank=True, max_length=255)),
                ("branch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_attributes", to="organizations.branch")),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_attributes", to="organizations.company")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="attribute", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "users_attributes",
            },
        ),
    ]
