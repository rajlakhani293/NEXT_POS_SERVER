from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_user_language_user_theme"),
    ]

    operations = [
        migrations.DeleteModel(
            name="OtpRequest",
        ),
    ]
