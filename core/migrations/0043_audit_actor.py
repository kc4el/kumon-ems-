from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0042_shift_swap_participants"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AddField(
            model_name="employeeauditlog", name="actor",
            field=models.ForeignKey(blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employee_audit_events", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="employeeauditlog", name="actor_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
