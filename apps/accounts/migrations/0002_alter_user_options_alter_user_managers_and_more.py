# Restored migration state after the interrupted user auth refactor.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='auth_provider',
        ),
        migrations.RemoveField(
            model_name='user',
            name='google_sub',
        ),
        migrations.RemoveField(
            model_name='user',
            name='is_email_verified',
        ),
        migrations.RemoveField(
            model_name='user',
            name='is_phone_verified',
        ),
        migrations.RemoveField(
            model_name='user',
            name='onboarding_completed',
        ),
    ]
