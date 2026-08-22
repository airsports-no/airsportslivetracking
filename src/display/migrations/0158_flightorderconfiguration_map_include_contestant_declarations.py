from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0157_scorecard_anr_auxiliary_route_penalties"),
    ]

    operations = [
        migrations.AddField(
            model_name="flightorderconfiguration",
            name="map_include_contestant_declarations",
            field=models.BooleanField(
                default=True,
                help_text="If this is set, contestant-specific maps and flight orders will render declaration-compiled contestant route data when available. Disable to use the generic task map instead.",
            ),
        ),
    ]
