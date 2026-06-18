from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("promotions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderscoupon",
            name="name",
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name="orderscoupon",
            name="discount_value",
            field=models.DecimalField(decimal_places=5, max_digits=18),
        ),
        migrations.AlterField(
            model_name="orderscoupon",
            name="discount_amount",
            field=models.DecimalField(db_column="value", decimal_places=5, default=0, max_digits=18),
        ),
    ]
