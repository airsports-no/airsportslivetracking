import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0191_navigationtask_show_live_score_in_app"),
    ]

    operations = [
        migrations.CreateModel(
            name="MobileAppActivity",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS")], max_length=10)),
                (
                    "app_version",
                    models.CharField(blank=True, default="", help_text="The version name, e.g. 2.0.0.", max_length=40),
                ),
                (
                    "app_build",
                    models.CharField(
                        blank=True, default="", help_text="Android versionCode / iOS build number.", max_length=20
                    ),
                ),
                ("first_seen", models.DateTimeField(auto_now_add=True)),
                ("last_seen", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mobile_app_activity",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-last_seen",), "unique_together": {("user", "platform")}},
        ),
    ]
