from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0184_push_scoring_started_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userentitlementgrant",
            name="kind",
            field=models.CharField(
                choices=[
                    ("task_type_group", "Task-type group"),
                    ("app_tracking", "Free app tracking (no subscription needed)"),
                ],
                default="task_type_group",
                help_text="What kind of thing is being granted; determines how 'value' is interpreted.",
                max_length=40,
            ),
        ),
    ]
