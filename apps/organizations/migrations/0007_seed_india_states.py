from django.db import migrations
from django.utils.text import slugify


INDIA_STATES = [
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
]


def seed_india_states(apps, schema_editor):
    StateMaster = apps.get_model("organizations", "StateMaster")
    for state_name in INDIA_STATES:
        StateMaster.objects.get_or_create(
            code=slugify(state_name),
            defaults={"name": state_name, "status": 0},
        )


def remove_india_states(apps, schema_editor):
    StateMaster = apps.get_model("organizations", "StateMaster")
    StateMaster.objects.filter(code__in=[slugify(name) for name in INDIA_STATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0006_statemaster"),
    ]

    operations = [
        migrations.RunPython(seed_india_states, remove_india_states),
    ]
