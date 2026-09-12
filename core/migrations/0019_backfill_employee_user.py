from django.db import migrations


def backfill_users(apps, schema_editor):
    from core.migrations_compat import backfill_employee_users

    backfill_employee_users()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_employee_user"),
    ]

    operations = [
        migrations.RunPython(backfill_users, migrations.RunPython.noop),
    ]
