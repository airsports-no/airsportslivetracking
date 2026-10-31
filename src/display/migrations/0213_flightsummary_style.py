from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0212_flightsummary_sections_analysis"),
    ]

    operations = [
        migrations.AddField(
            model_name="flightsummary",
            name="style",
            field=models.CharField(default="debrief", max_length=20),
        ),
        migrations.AlterUniqueTogether(
            name="flightsummary",
            unique_together={("contestant", "track_version", "score_version", "prompt_version", "style")},
        ),
    ]
