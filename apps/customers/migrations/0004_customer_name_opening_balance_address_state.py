from django.db import migrations, models
import django.db.models.deletion


def combine_customer_names(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    for customer in Customer.objects.all():
        first_name = getattr(customer, "first_name", "") or ""
        last_name = getattr(customer, "last_name", "") or ""
        name = f"{first_name} {last_name}".strip() or "Customer"
        customer.name = name
        customer.save(update_fields=["name"])


def copy_address_fields(apps, schema_editor):
    CustomerAddress = apps.get_model("customers", "CustomerAddress")
    for address in CustomerAddress.objects.all():
        address.address_line_1 = getattr(address, "address_1", "") or ""
        address.pincode = getattr(address, "postal_code", "") or ""
        address.save(update_fields=["address_line_1", "pincode"])


def backfill_address_company(apps, schema_editor):
    CustomerAddress = apps.get_model("customers", "CustomerAddress")
    for address in CustomerAddress.objects.select_related("customer").all():
        if address.customer_id and getattr(address.customer, "company_id", None):
            address.company_id = address.customer.company_id
            address.save(update_fields=["company_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0003_alter_customer_status_alter_customeraddress_status_and_more"),
        ("organizations", "0008_company_branch_state_relation"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="name",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.RunPython(combine_customer_names, migrations.RunPython.noop),
        migrations.RenameField(
            model_name="customer",
            old_name="tax_number",
            new_name="gst_number",
        ),
        migrations.AddField(
            model_name="customer",
            name="opening_balance",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="customeraddress",
            name="address_line_1",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="customeraddress",
            name="pincode",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.RunPython(copy_address_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="customer",
            name="first_name",
        ),
        migrations.RemoveField(
            model_name="customer",
            name="last_name",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="first_name",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="last_name",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="phone",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="email",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="company",
        ),
        migrations.AddField(
            model_name="customeraddress",
            name="company",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(class)ss",
                to="organizations.company",
            ),
        ),
        migrations.RunPython(backfill_address_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="customeraddress",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="%(class)ss",
                to="organizations.company",
            ),
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="address_1",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="address_2",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="country",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="postal_code",
        ),
        migrations.RemoveField(
            model_name="customeraddress",
            name="state",
        ),
        migrations.AddField(
            model_name="customeraddress",
            name="state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="customer_addresses",
                to="organizations.statemaster",
            ),
        ),
        migrations.AlterField(
            model_name="customeraddress",
            name="address_type",
            field=models.CharField(
                choices=[("billing", "Billing"), ("shipping", "Shipping")],
                max_length=20,
            ),
        ),
        migrations.AlterModelOptions(
            name="customer",
            options={"ordering": ["name", "id"]},
        ),
    ]
