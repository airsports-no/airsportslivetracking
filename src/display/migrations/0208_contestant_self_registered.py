from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0207_navigation_task_manager_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="contestant",
            name="self_registered",
            field=models.BooleanField(
                default=False,
                editable=False,
                help_text="Is true if the pilot booked this flight themselves (self management) rather than a contest manager adding it. The pilot's flight order is then e-mailed automatically, for tasks requiring a declaration once it has been saved.",
            ),
        ),
    ]
