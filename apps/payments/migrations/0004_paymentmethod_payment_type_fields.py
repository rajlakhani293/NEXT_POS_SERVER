import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_identifier(apps, schema_editor):
    PaymentMethod = apps.get_model("payments", "PaymentMethod")
    for method in PaymentMethod.objects.all().order_by("id"):
        identifier = method.code or f"payment-method-{method.id}"
        method.identifier = identifier
        method.save(update_fields=["identifier"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("payments", "0003_alter_paymentmethod_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="identifier",
            field=models.SlugField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="readonly",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_methods",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_identifier, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="paymentmethod",
            name="identifier",
            field=models.SlugField(max_length=120),
        ),
        migrations.AlterUniqueTogether(
            name="paymentmethod",
            unique_together={("branch", "code"), ("branch", "identifier")},
        ),
    ]
