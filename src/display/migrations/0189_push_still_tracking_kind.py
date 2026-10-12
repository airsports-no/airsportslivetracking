from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0188_contestanttrack_last_timed_gate"),
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
                    ("still_tracking", "Tracking still on after the flight window closed"),
                ],
                max_length=40,
            ),
        ),
    ]
