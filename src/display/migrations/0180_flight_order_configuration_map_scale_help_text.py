from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0179_contestcreator_group_add_editableroute_permission"),
    ]

    operations = [
        migrations.AlterField(
            model_name="flightorderconfiguration",
            name="map_scale",
            field=models.IntegerField(
                choices=[
                    (25, "1:25,000"),
                    (50, "1:50,000"),
                    (100, "1:100,000"),
                    (150, "1:150,000"),
                    (200, "1:200,000"),
                    (250, "1:250,000"),
                    (300, "1:300,000"),
                    (0, "Fit page"),
                ],
                default=0,
                help_text="The printed map's scale bar shows the map's actual measured scale, which can "
                "differ from this selected value by a small fraction of a percent - an inherent property "
                "of the underlying map projection, not an error.",
            ),
        ),
    ]
