import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0216_photo_unique_name_per_route"),
    ]

    operations = [
        migrations.AlterField(
            model_name="flightorderconfiguration",
            name="map_dpi",
            field=models.IntegerField(
                default=300,
                validators=[
                    django.core.validators.MinValueValidator(100),
                    django.core.validators.MaxValueValidator(300),
                ],
            ),
        ),
    ]
