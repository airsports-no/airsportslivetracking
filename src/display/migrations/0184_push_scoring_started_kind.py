from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0183_mobile_devices_and_push_log"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pushnotificationlog",
            name="kind",
            field=models.CharField(
                choices=[
                    ("tracking_window_opens", "Tracking window opens soon"),
                    ("not_tracking", "Flight started but no positions received"),
                    ("scoring_started", "Scoring started for the flight"),
                ],
                max_length=40,
            ),
        ),
    ]
