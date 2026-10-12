import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0189_push_still_tracking_kind"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContestAnnouncement",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.CharField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "people_reached",
                    models.PositiveIntegerField(default=0, help_text="How many people got the push notification."),
                ),
                (
                    "contest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="announcements", to="display.contest"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "navigation_task",
                    models.ForeignKey(
                        blank=True,
                        help_text="Limits the announcement to the crews of this task. Empty: every crew registered in the contest.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="display.navigationtask",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AlterField(
            model_name="pushnotificationlog",
            name="kind",
            field=models.CharField(
                choices=[
                    ("tracking_window_opens", "Tracking window opens soon"),
                    ("not_tracking", "Flight started but no positions received"),
                    ("scoring_started", "Scoring started for the flight"),
                    ("still_tracking", "Tracking still on after the flight window closed"),
                    ("flight_scored", "The flight has been scored"),
                ],
                max_length=40,
            ),
        ),
    ]
