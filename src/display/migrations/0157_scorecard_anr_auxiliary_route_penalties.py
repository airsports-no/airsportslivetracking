from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0156_scorecard_task_specific_runtime_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="scorecard",
            name="anr_route_to_sp_penalty",
            field=models.FloatField(default=200),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="anr_route_from_fp_penalty",
            field=models.FloatField(default=200),
        ),
    ]
