import django.db.models.deletion
from django.db import migrations, models


def ensure_reward_system_coupon(apps, schema_editor):
    RewardSystem = apps.get_model("rewards", "RewardSystem")
    if RewardSystem.objects.filter(coupon_id__isnull=True).exists():
        raise RuntimeError(
            "Reward systems without coupon exist. Assign a coupon before applying this migration."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("rewards", "0003_align_reward_system_structure"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="rewardsystem",
            unique_together=set(),
        ),
        migrations.RunPython(ensure_reward_system_coupon, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="rewardsystem",
            name="code",
        ),
        migrations.AlterField(
            model_name="rewardsystem",
            name="coupon",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reward_systems",
                to="promotions.coupon",
            ),
        ),
    ]
