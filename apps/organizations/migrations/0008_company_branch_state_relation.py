from django.db import migrations, models
import django.db.models.deletion


def map_state_names(apps, schema_editor):
    Company = apps.get_model("organizations", "Company")
    Branch = apps.get_model("organizations", "Branch")
    StateMaster = apps.get_model("organizations", "StateMaster")

    state_map = {
        state.name.strip().lower(): state.id
        for state in StateMaster.objects.all()
    }

    for company in Company.objects.all():
        state_name = (getattr(company, "state_name_old", "") or "").strip().lower()
        state_id = state_map.get(state_name)
        if state_id:
            company.state_id = state_id
            company.save(update_fields=["state"])

    for branch in Branch.objects.all():
        state_name = (getattr(branch, "state_name_old", "") or "").strip().lower()
        state_id = state_map.get(state_name)
        if state_id:
            branch.state_id = state_id
            branch.save(update_fields=["state"])


def unmap_state_names(apps, schema_editor):
    Company = apps.get_model("organizations", "Company")
    Branch = apps.get_model("organizations", "Branch")

    for company in Company.objects.select_related("state").all():
        if company.state:
            company.state_name_old = company.state.name
            company.save(update_fields=["state_name_old"])

    for branch in Branch.objects.select_related("state").all():
        if branch.state:
            branch.state_name_old = branch.state.name
            branch.save(update_fields=["state_name_old"])


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0007_seed_india_states"),
    ]

    operations = [
        migrations.RenameField(
            model_name="company",
            old_name="state",
            new_name="state_name_old",
        ),
        migrations.RenameField(
            model_name="branch",
            old_name="state",
            new_name="state_name_old",
        ),
        migrations.AddField(
            model_name="company",
            name="state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="companies",
                to="organizations.statemaster",
            ),
        ),
        migrations.AddField(
            model_name="branch",
            name="state",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="branches",
                to="organizations.statemaster",
            ),
        ),
        migrations.RunPython(map_state_names, unmap_state_names),
        migrations.RemoveField(
            model_name="company",
            name="state_name_old",
        ),
        migrations.RemoveField(
            model_name="branch",
            name="state_name_old",
        ),
    ]
