from django.db import migrations, models


def normalize_coupon_type(apps, schema_editor):
    Coupon = apps.get_model("promotions", "Coupon")
    AppliedCoupon = apps.get_model("promotions", "AppliedCoupon")
    Coupon.objects.filter(type="flat").update(type="flat_discount")
    Coupon.objects.filter(type="percentage").update(type="percentage_discount")
    AppliedCoupon.objects.filter(type="flat").update(type="flat_discount")
    AppliedCoupon.objects.filter(type="percentage").update(type="percentage_discount")


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0003_couponcustomergroup_couponcustomer"),
    ]

    operations = [
        migrations.RenameField(
            model_name="coupon",
            old_name="discount_type",
            new_name="type",
        ),
        migrations.RenameField(
            model_name="coupon",
            old_name="max_discount_amount",
            new_name="maximum_cart_value",
        ),
        migrations.RenameField(
            model_name="coupon",
            old_name="usage_limit",
            new_name="limit_usage",
        ),
        migrations.RenameField(
            model_name="coupon",
            old_name="ends_at",
            new_name="valid_until",
        ),
        migrations.RenameField(
            model_name="appliedcoupon",
            old_name="discount_type",
            new_name="type",
        ),
        migrations.RunPython(normalize_coupon_type, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="coupon",
            name="type",
            field=models.CharField(
                choices=[
                    ("flat_discount", "Flat Discount"),
                    ("percentage_discount", "Percentage Discount"),
                ],
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="appliedcoupon",
            name="type",
            field=models.CharField(max_length=30),
        ),
        migrations.AddField(
            model_name="coupon",
            name="valid_hours_start",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="coupon",
            name="valid_hours_end",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.RemoveField(
            model_name="coupon",
            name="starts_at",
        ),
        migrations.RemoveField(
            model_name="coupon",
            name="per_customer_limit",
        ),
        migrations.RemoveField(
            model_name="coupon",
            name="applies_to_all_products",
        ),
    ]
