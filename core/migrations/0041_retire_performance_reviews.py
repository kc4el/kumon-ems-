from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0040_pay_estimates")]

    # Keep the legacy table and its data until its owner explicitly approves a purge.
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[migrations.DeleteModel(name="PerformanceReview")],
        ),
    ]
