from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0186_photo_observation"),
    ]

    operations = [
        migrations.AddField(
            model_name="navigationtask",
            name="allow_observation_registration",
            field=models.BooleanField(
                default=False,
                help_text="If checked, crews can register observation photos from the app while they are being tracked. Observations are then scored, and photos that were not marked count as missed when the flight ends.",
            ),
        ),
    ]
