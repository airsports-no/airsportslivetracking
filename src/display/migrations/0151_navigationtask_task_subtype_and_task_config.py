from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0150_club_manager_membership_audit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="navigationtask",
            name="task_config",
            field=models.JSONField(blank=True, default=dict, help_text="Subtype-specific task configuration"),
        ),
        migrations.AddField(
            model_name="navigationtask",
            name="task_subtype",
            field=models.CharField(
                blank=True,
                help_text="Detailed task subtype semantics layered on top of the coarse calculator family",
                max_length=100,
                null=True,
            ),
        ),
    ]
