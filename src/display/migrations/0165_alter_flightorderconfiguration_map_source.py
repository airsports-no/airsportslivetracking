from django.db import migrations, models

import display.flight_order_and_maps.map_plotter_shared_utilities


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0164_scorelogentry_bounded_message_and_idempotency_constraint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="flightorderconfiguration",
            name="map_source",
            field=models.CharField(
                blank=True,
                choices=display.flight_order_and_maps.map_plotter_shared_utilities.get_map_choices,
                default="cyclosm",
                max_length=50,
            ),
        ),
    ]
