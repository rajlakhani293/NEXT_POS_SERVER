from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_userattribute"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                condition=~models.Q(("full_name", "")) & models.Q(("status__in", [0, 1])),
                fields=("branch", "full_name"),
                name="accounts_user_branch_full_name_unique_active",
            ),
        ),
    ]
