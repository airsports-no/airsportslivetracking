from django.db import migrations


def backfill_unified_map_source(apps, schema_editor):
    FlightOrderConfiguration = apps.get_model("display", "FlightOrderConfiguration")

    for configuration in FlightOrderConfiguration.objects.exclude(map_user_source=None):
        configuration.map_source = f"user_uploaded:{configuration.map_user_source_id}"
        configuration.save(update_fields=["map_source"])


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0139_useruploadedmap_maximum_latitude_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_unified_map_source, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="flightorderconfiguration",
            name="map_user_source",
        ),
    ]
