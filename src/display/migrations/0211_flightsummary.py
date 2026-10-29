import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0210_contestanttrack_next_timed_gate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FlightSummary",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("track_version", models.IntegerField()),
                ("score_version", models.IntegerField()),
                ("prompt_version", models.IntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("done", "Done"), ("failed", "Failed")],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("text", models.TextField(blank=True, default="")),
                ("error", models.CharField(blank=True, default="", max_length=500)),
                ("model", models.CharField(blank=True, default="", max_length=100)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("cost_usd", models.DecimalField(decimal_places=6, default=0, max_digits=10)),
                ("requested_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contestant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flight_summaries",
                        to="display.contestant",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("contestant", "track_version", "score_version", "prompt_version")},
                "indexes": [models.Index(fields=["requested_by", "requested_at"], name="flight_summary_quota_idx")],
            },
        ),
    ]
