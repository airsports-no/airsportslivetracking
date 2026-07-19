from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0141_stage_a_shared_storage_placeholder"),
    ]

    operations = [
        migrations.AddField(
            model_name="flightorderconfiguration",
            name="map_include_openaip_overlay",
            field=models.BooleanField(
                default=False,
                help_text="If true, OpenAIP is rendered on top of the selected map source in generated maps.",
            ),
        ),
    ]
