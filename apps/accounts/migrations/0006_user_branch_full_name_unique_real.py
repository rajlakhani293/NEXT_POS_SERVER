from django.db import migrations


def normalize_user_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    seen = set()

    for user in User.objects.order_by("branch_id", "id"):
        branch_key = user.branch_id or 0
        base_name = (user.full_name or "").strip() or (user.username or "").strip() or f"user-{user.id}"
        candidate = base_name
        candidate_key = (branch_key, candidate.lower())

        if candidate_key in seen:
            candidate = f"{base_name} {user.id}"
            candidate_key = (branch_key, candidate.lower())
            while candidate_key in seen:
                candidate = f"{base_name} {user.id}-{len(seen)}"
                candidate_key = (branch_key, candidate.lower())

        if user.full_name != candidate:
            user.full_name = candidate
            user.save(update_fields=["full_name"])

        seen.add(candidate_key)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_branch_full_name_unique"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="user",
            name="accounts_user_branch_full_name_unique_active",
        ),
        migrations.RunPython(normalize_user_names, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="user",
            unique_together={("branch", "full_name")},
        ),
    ]
