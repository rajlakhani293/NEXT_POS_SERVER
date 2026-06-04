from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rewards", "0002_alter_customerrewardbalance_status_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="rewardsystem",
            old_name="target_points",
            new_name="target",
        ),
        migrations.RenameField(
            model_name="rewardrule",
            old_name="min_amount",
            new_name="from_amount",
        ),
        migrations.RenameField(
            model_name="rewardrule",
            old_name="max_amount",
            new_name="to_amount",
        ),
        migrations.RenameField(
            model_name="rewardrule",
            old_name="points",
            new_name="reward",
        ),
        migrations.AlterModelOptions(
            name="rewardrule",
            options={"ordering": ["from_amount"]},
        ),
        migrations.AlterField(
            model_name="rewardsystem",
            name="target",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="rewardrule",
            name="from_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name="rewardrule",
            name="to_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name="rewardrule",
            name="reward",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
