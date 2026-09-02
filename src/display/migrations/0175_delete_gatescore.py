from django.db import migrations


class Migration(migrations.Migration):
    """
    Migration D of Phase 2e of the scorecard-system review roadmap. GateScore stopped being
    written to once every consumer (default_scorecards/*.py seed files,
    ScorecardNestedSerialiser.update(), GateScoreForm, the two now-removed mirror signals)
    was reworked in a prior PR to read/write Scorecard.config["gates"][gate_type] directly
    instead. Dropping the table for real - it was kept this long purely as a rollback/
    verification snapshot of the pre-Phase-2 data.
    """

    dependencies = [
        ("display", "0174_scorecard_drop_legacy_columns"),
    ]

    operations = [
        migrations.DeleteModel(name="GateScore"),
    ]
