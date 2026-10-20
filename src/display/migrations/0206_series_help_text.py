from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0205_series_request"),
    ]

    operations = [
        migrations.AlterField(
            model_name="series",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="A public series is visible to everybody and can only contain public contests. A private series is only visible to the people who have been given access to it.",
            ),
        ),
    ]
