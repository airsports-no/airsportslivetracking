import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0185_userentitlementgrant_app_tracking"),
    ]

    operations = [
        migrations.CreateModel(
            name="PhotoObservation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("photo_name", models.CharField(max_length=200)),
                ("time", models.DateTimeField()),
                ("latitude", models.FloatField()),
                ("longitude", models.FloatField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("scored", models.BooleanField(default=False)),
                ("status", models.CharField(blank=True, default="", max_length=40)),
                ("error_m", models.FloatField(blank=True, null=True)),
                ("error_mm", models.FloatField(blank=True, null=True)),
                ("score_fraction", models.FloatField(default=0.0)),
                ("points", models.FloatField(default=0.0)),
                ("metres_per_mm", models.FloatField(blank=True, null=True)),
                ("projected_latitude", models.FloatField(blank=True, null=True)),
                ("projected_longitude", models.FloatField(blank=True, null=True)),
                ("photo_projected_latitude", models.FloatField(blank=True, null=True)),
                ("photo_projected_longitude", models.FloatField(blank=True, null=True)),
                (
                    "contestant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photo_observations",
                        to="display.contestant",
                    ),
                ),
                (
                    "photo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="observations",
                        to="display.photo",
                    ),
                ),
            ],
            options={
                "ordering": ("time",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("contestant", "photo"), name="unique_photo_observation_per_photo"
                    )
                ],
            },
        ),
    ]
