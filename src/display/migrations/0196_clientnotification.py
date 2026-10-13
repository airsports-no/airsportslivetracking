import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0195_mobileappactivity_msfs_platform"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientNotification",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
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
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField()),
                ("navigation_task_id", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contestant",
                    models.ForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="display.contestant"
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="client_notifications",
                        to="display.person",
                    ),
                ),
            ],
            options={
                "ordering": ("-id",),
                "indexes": [models.Index(fields=["person", "id"], name="client_notification_person")],
            },
        ),
    ]
