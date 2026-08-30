from django.db import migrations, models
from django.db.models import Count


def dedupe_playing_cards(apps, schema_editor):
    """
    Removes duplicate PlayingCard rows created by a bug where a live-calculator restart
    mid-flight replayed the whole track from the beginning - PokerCalculator.passed_gates
    (in-memory only) rebuilds empty on restart, so every already-passed poker gate re-fired
    its PokerGatePassedEvent and dealt a second card at the same waypoint for the same
    contestant.

    For each (contestant, waypoint_name) group with more than one card (waypoint_name IS NOT
    NULL - a NULL waypoint was never dealt automatically and isn't part of this bug), keeps
    the earliest row (lowest pk) and deletes the rest. Hand evaluation (PlayingCard.evaluate_hand)
    recomputes fresh from whatever cards currently exist each time it's called - it isn't
    incrementally stored anywhere - so removing the extra rows is sufficient to correct any
    future score computation; nothing else needs adjusting.

    This must run before the AlterUniqueTogether below, which those duplicates would
    otherwise violate.
    """
    PlayingCard = apps.get_model("display", "PlayingCard")

    duplicate_groups = list(
        PlayingCard.objects.exclude(waypoint_name=None)
        .values("contestant_id", "waypoint_name")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )

    if not duplicate_groups:
        return

    print(f"\n  Found {len(duplicate_groups)} duplicate PlayingCard group(s) to clean up.")

    for group in duplicate_groups:
        matching = PlayingCard.objects.filter(
            contestant_id=group["contestant_id"], waypoint_name=group["waypoint_name"]
        ).order_by("pk")
        keep = matching.first()
        extras = list(matching.exclude(pk=keep.pk))
        if not extras:
            continue
        print(
            f"  contestant={group['contestant_id']} waypoint={group['waypoint_name']!r}: "
            f"removing {len(extras)} duplicate card(s) (pks={[e.pk for e in extras]}), keeping pk={keep.pk}"
        )
        for extra in extras:
            extra.delete()


def noop_reverse(apps, schema_editor):
    # Deleted duplicate rows are not reconstructible - this migration is intentionally
    # one-directional, matching 0163_dedupe_scorelogentry_and_correct_totals.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0168_delete_stale_cima_gate_scores"),
    ]

    operations = [
        migrations.RunPython(dedupe_playing_cards, noop_reverse),
        migrations.AlterUniqueTogether(
            name="playingcard",
            unique_together={("contestant", "waypoint_name")},
        ),
    ]
