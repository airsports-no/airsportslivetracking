from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0158_flightorderconfiguration_map_include_contestant_declarations"),
    ]

    operations = [
        migrations.AddField(
            model_name="photo",
            name="is_decoy",
            field=models.BooleanField(
                default=False,
                help_text="If true, this is a decoy/false photo with no corresponding real route feature.",
            ),
        ),
        migrations.AddField(
            model_name="photo",
            name="decoy_course",
            field=models.FloatField(
                blank=True,
                null=True,
                help_text="Course (degrees) printed/oriented on a decoy photo. Only used when is_decoy is true.",
            ),
        ),
    ]
