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
                default=True,
                help_text="If checked, pilots get live feedback in the mobile app while they fly: a running update of their score and gate timing in training mode. Uncheck it for competitions where the pilot should not see any of this until the results are published.",
            ),
        ),
    ]
