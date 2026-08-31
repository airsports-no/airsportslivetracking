from django.db import migrations

OLD_NAME = "AirSport Challenge 2023"
CANONICAL_NAME = "Air Sport Challenge 2023"


def merge_duplicate_scorecard(apps, schema_editor):
    """
    A rename-target typo in default_scorecard_airsport_challenge.get_default_scorecard()
    (fixed alongside this migration) spawned a second, permanently out-of-sync Scorecard row
    named "AirSport Challenge 2023" instead of merging into the canonical "Air Sport Challenge
    2023" row every subsequent get_default_scorecard() run actually keeps updated. Reassign any
    NavigationTask referencing the stale duplicate onto the canonical row, then remove it -
    original_scorecard is only ever read live for .calculator/.name (see navigation_task.py,
    views.py, serialisers.py, signals.py), never for scoring-parameter fields, so this has no
    effect on any task's already-independent, already-copied .scorecard (the actual live scoring
    config) or on any already-computed score.
    """
    Scorecard = apps.get_model("display", "Scorecard")
    NavigationTask = apps.get_model("display", "NavigationTask")

    try:
        old = Scorecard.objects.get(name=OLD_NAME)
    except Scorecard.DoesNotExist:
        return
    try:
        canonical = Scorecard.objects.get(name=CANONICAL_NAME)
    except Scorecard.DoesNotExist:
        # No canonical row yet on this environment - the duplicate IS the only copy, just
        # rename it in place rather than deleting the only scorecard tasks reference.
        old.name = CANONICAL_NAME
        old.save(update_fields=["name"])
        return

    NavigationTask.objects.filter(original_scorecard=old).update(original_scorecard=canonical)
    NavigationTask.objects.filter(scorecard=old).update(scorecard=canonical)
    old.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0169_dedupe_playingcard_and_idempotency_constraint"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_scorecard, migrations.RunPython.noop),
    ]
