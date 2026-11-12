from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0041_retire_performance_reviews")]

    operations = [
        migrations.AddField(
            model_name="shiftswap", name="requester_employee",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="requested_shift_swaps", to="core.employee"),
        ),
        migrations.AddField(
            model_name="shiftswap", name="target_employee",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name="targeted_shift_swaps", to="core.employee"),
        ),
    ]
