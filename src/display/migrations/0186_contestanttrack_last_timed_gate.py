from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0185_userentitlementgrant_app_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="contestanttrack",
            name="last_timed_gate",
            field=models.CharField(default="", max_length=100),
        ),
        migrations.AddField(
            model_name="contestanttrack",
            name="last_timed_gate_time_offset",
            field=models.FloatField(default=0),
        ),
    ]
