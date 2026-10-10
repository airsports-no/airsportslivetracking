import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0182_person_email_unique"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileDevice",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS")], max_length=10)),
                ("push_token", models.CharField(max_length=512)),
                ("token_hash", models.CharField(editable=False, max_length=64, unique=True)),
                ("app_version", models.CharField(blank=True, default="", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="mobile_devices", to="display.person"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PushNotificationLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("tracking_window_opens", "Tracking window opens soon"),
                            ("not_tracking", "Flight started but no positions received"),
                        ],
                        max_length=40,
                    ),
                ),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                ("devices_reached", models.PositiveIntegerField(default=0)),
                (
                    "contestant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="display.contestant"),
                ),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="display.person")),
            ],
        ),
        migrations.AddConstraint(
            model_name="pushnotificationlog",
            constraint=models.UniqueConstraint(
                fields=("kind", "contestant", "person"), name="unique_push_per_contestant_person"
            ),
        ),
    ]
