import display.models.contest
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0218_contestanttrack_quality_scoring_scorelogentry_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="overall_result_method",
            field=models.CharField(
                choices=[("sum_of_scores", "Sum of task scores"), ("standings_points", "Standings points per task placing")],
                default="sum_of_scores",
                help_text="How the overall result is made when scores are summed automatically: add the task scores, or give points for the place in each task (FAI Annex 9, 6.7.7) and add the points. With standings points the highest total always wins.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="contest",
            name="standings_points_table",
            field=models.JSONField(
                blank=True,
                default=display.models.contest.default_standings_points_table,
                help_text="Points for first, second, third… place in a task. Used with standings points; later places get nothing.",
            ),
        ),
    ]
