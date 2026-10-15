"""Add the supported statutory-record upload category."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_authenticatordevice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="onboardingdocument",
            name="doc_type",
            field=models.CharField(
                choices=[
                    ("NBI", "NBI Clearance"),
                    ("BIR2316", "BIR Form 2316"),
                    ("PSA", "PSA Birth Certificate"),
                    ("contract", "Signed Employment Contract"),
                    ("government_records", "SSS / PhilHealth / Pag-IBIG Records"),
                ],
                max_length=20,
            ),
        ),
    ]
