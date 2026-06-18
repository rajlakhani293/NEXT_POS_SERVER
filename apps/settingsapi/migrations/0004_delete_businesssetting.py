from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("settingsapi", "0003_add_options_and_queue_tables"),
    ]

    operations = [
        migrations.DeleteModel(
            name="BusinessSetting",
        ),
    ]
