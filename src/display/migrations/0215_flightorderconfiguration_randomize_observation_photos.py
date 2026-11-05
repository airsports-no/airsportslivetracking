from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0214_flightsummary_utf8mb4"),
    ]

    operations = [
        migrations.AddField(
            model_name="flightorderconfiguration",
            name="randomize_observation_photos",
            field=models.BooleanField(
                default=False,
                help_text="If set, the observation photos are in a random order, the same for every contestant of the task and every time the flight order is made. Otherwise they are in the order of their names. Either way the photos are numbered by their place in the flight order, never by name, which could give away the order of the route.",
            ),
        ),
    ]
