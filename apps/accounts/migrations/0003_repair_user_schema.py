from django.db import migrations


RESTORED_FIELDS = [
    "last_login",
    "is_superuser",
    "first_name",
    "last_name",
    "is_staff",
    "is_active",
    "date_joined",
    "full_name",
    "profile_image",
    "phone",
    "is_cashier",
    "is_store_manager",
    "deleted_at",
    "role",
]

TEMPORARY_FIELDS = [
    "activation_expiration",
    "activation_token",
    "created_at",
    "remember_token",
    "total_sales",
    "total_sales_count",
    "updated_at",
]


def repair_user_schema(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    connection = schema_editor.connection
    user_table = User._meta.db_table

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor,
                user_table,
            )
        }

    for field_name in RESTORED_FIELDS:
        field = User._meta.get_field(field_name)
        if field.column not in columns:
            schema_editor.add_field(User, field)
            columns.add(field.column)

    table_names = set(connection.introspection.table_names())
    for field_name in ["groups", "user_permissions"]:
        through_model = User._meta.get_field(field_name).remote_field.through
        if through_model._meta.db_table not in table_names:
            schema_editor.create_model(through_model)
            table_names.add(through_model._meta.db_table)

    relation_table = "accounts_userrolerelation"
    if relation_table in table_names:
        quote = connection.ops.quote_name
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE {quote(user_table)} AS users
                INNER JOIN {quote(relation_table)} AS relations
                    ON relations.user_id = users.id
                    AND relations.status = 0
                SET users.role_id = relations.role_id
                WHERE users.role_id IS NULL
                """
            )
        schema_editor.execute(f"DROP TABLE {quote(relation_table)}")

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            UPDATE {connection.ops.quote_name(user_table)}
            SET full_name = username
            WHERE full_name = '' OR full_name IS NULL
            """
        )

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor,
                user_table,
            )
        }

    for field_name in TEMPORARY_FIELDS:
        if field_name in columns:
            schema_editor.execute(
                f"ALTER TABLE {connection.ops.quote_name(user_table)} "
                f"DROP COLUMN {connection.ops.quote_name(field_name)}"
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0002_alter_user_options_alter_user_managers_and_more"),
    ]

    operations = [
        migrations.RunPython(repair_user_schema, migrations.RunPython.noop),
    ]
