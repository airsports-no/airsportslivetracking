from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Migration A of Phase 2 of the scorecard-system review roadmap (JSON-blob-backed scoring
    config - see the roadmap doc, saved outside the repo, for full context). Purely additive:
    adds the new column with no data yet and no consumer-facing behavior change. Population
    happens in migration 0172; the old columns are only renamed out of the way (not touched
    here) in migration 0173, once 0172 has copied everything into config.
    """

    dependencies = [
        ("display", "0170_merge_duplicate_airsport_challenge_scorecard"),
    ]

    operations = [
        migrations.AddField(
            model_name="scorecard",
            name="config",
            field=models.JSONField(default=dict),
        ),
    ]
