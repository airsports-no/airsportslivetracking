from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0130_contestantreceivedposition_projected_x_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="useruploadedmap",
            name="processing_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("ready", "Ready"), ("failed", "Failed")],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="useruploadedmap",
            name="processing_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunSQL(
            sql="UPDATE display_useruploadedmap SET processing_status = 'ready' WHERE thumbnail IS NOT NULL AND thumbnail != '';",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
