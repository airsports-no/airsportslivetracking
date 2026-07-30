from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0155_task_type_group_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="scorecard",
            name="compulsory_timing_tolerance_seconds",
            field=models.IntegerField(default=10),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="maximum_task_duration_minutes",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="maximum_task_duration_penalty",
            field=models.FloatField(default=100),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="fuel_deadline_penalty",
            field=models.FloatField(default=100),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="duration_normalization_policy",
            field=models.CharField(blank=True, choices=[("", "---------"), ("raw_minutes", "Raw minutes")], default="", max_length=40),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="duration_residual_fuel_required",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="circle_radius_min_m",
            field=models.FloatField(default=200),
        ),
        migrations.AddField(
            model_name="scorecard",
            name="circle_radius_max_m",
            field=models.FloatField(default=750),
        ),
    ]
