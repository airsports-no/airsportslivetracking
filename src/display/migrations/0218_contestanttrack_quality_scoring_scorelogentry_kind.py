from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0217_alter_flightorderconfiguration_map_dpi_default_300"),
    ]

    operations = [
        migrations.AddField(
            model_name="contestanttrack",
            name="raw_quality",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="contestanttrack",
            name="quality_start",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contestanttrack",
            name="quality_theoretical_maximum",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contestanttrack",
            name="percentage_penalty",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="contestanttrack",
            name="quality_breakdown",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="scorelogentry",
            name="score_type",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="scorelogentry",
            name="score_kind",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
