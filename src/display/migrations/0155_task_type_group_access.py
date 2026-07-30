from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0154_administrativepenalty_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="tokentype",
            name="task_type_groups",
            field=models.JSONField(blank=True, default=list, help_text="Task-type groups this token package may be used for. Leave empty to use the default legacy-only behavior unless free defaults or another source allow more groups."),
        ),
        migrations.AddField(
            model_name="accessgrant",
            name="task_type_groups",
            field=models.JSONField(blank=True, default=list, help_text="Task-type groups this access grant allows. Leave empty to use the default legacy-only behavior unless free defaults or another source allow more groups."),
        ),
    ]
