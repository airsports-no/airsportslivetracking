from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0206_series_help_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="navigationtask",
            name="notify_managers_on_start",
            field=models.BooleanField(
                default=False,
                help_text="If checked, everybody who manages the contest gets an e-mail when a contestant starts the task (when scoring of their flight starts). Useful for a cup where contestants fly the task on their own at different times.",
            ),
        ),
        migrations.AddField(
            model_name="navigationtask",
            name="notify_managers_on_finish",
            field=models.BooleanField(
                default=False,
                help_text="If checked, everybody who manages the contest gets an e-mail with the score when a contestant has finished the task: crossed the finish line, or their tracking window ended.",
            ),
        ),
    ]
