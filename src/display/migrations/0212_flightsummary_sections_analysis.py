from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0211_flightsummary"),
    ]

    operations = [
        migrations.AddField(
            model_name="flightsummary",
            name="headline",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="flightsummary",
            name="sections",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="flightsummary",
            name="analysis",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
