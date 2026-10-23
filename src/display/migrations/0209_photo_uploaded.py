from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0208_contestant_self_registered"),
    ]

    operations = [
        migrations.AddField(
            model_name="photo",
            name="uploaded",
            field=models.BooleanField(
                default=False,
                help_text="If true, file is a picture uploaded by the organiser, not the generated satellite image.",
            ),
        ),
    ]
