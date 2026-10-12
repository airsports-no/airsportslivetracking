from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0190_contest_announcements_and_flight_scored_push"),
    ]

    operations = [
        migrations.AddField(
            model_name="navigationtask",
            name="show_live_score_in_app",
            field=models.BooleanField(
                default=False,
                help_text="If checked, pilots see a running update of their score in the mobile app while they fly. Leave it off for competitions where the score should not be visible to the pilot until the results are published.",
            ),
        ),
    ]
