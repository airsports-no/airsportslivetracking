from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0193_simulatorquickstart"),
    ]

    operations = [
        migrations.AddField(
            model_name="simulatorquickstart",
            name="air_speed",
            field=models.FloatField(default=70, help_text="Cruise speed (knots) the practice flight is planned with."),
        ),
        migrations.AddField(
            model_name="simulatorquickstart",
            name="aircraft_registration",
            field=models.CharField(default="MSFS", help_text="Aircraft registration used for the practice team.", max_length=20),
        ),
        migrations.AddField(
            model_name="simulatorquickstart",
            name="club_name",
            field=models.CharField(default="MSFS pilots", help_text="Club used for the practice team.", max_length=200),
        ),
    ]
