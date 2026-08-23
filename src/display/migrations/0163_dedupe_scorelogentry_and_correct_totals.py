from django.db import migrations
from django.db.models import Count, F


IDEMPOTENCY_FIELDS = ("contestant_id", "time", "gate", "message", "points", "planned", "actual", "type")


def dedupe_score_log_entries(apps, schema_editor):
    """
    Removes duplicate ScoreLogEntry rows created by a historical bug (fixed
    in commit 94782a91/0122c7e0) where a restarted calculator could
    re-persist the same score event under a race/replay condition. All
    known duplicates predate the idempotent-restart feature entirely (see
    the query below run against the pre-cleanup dataset), so this is a
    one-time correction of legacy data, not an ongoing concern.

    For each group of exact duplicates (matching every field the current
    idempotency key checks), keeps the earliest row (lowest pk) and deletes
    the rest. The old bug unconditionally incremented GateCumulativeScore
    and ContestantTrack.score for every duplicate, so this also subtracts
    the removed rows' points from both to correct the resulting inflation -
    otherwise the audit-log cleanup alone would leave those running totals
    permanently inflated with no remaining log entries to explain why.

    This must run before 0164 adds the unique constraint those duplicates
    would otherwise violate.
    """
    ScoreLogEntry = apps.get_model("display", "ScoreLogEntry")
    GateCumulativeScore = apps.get_model("display", "GateCumulativeScore")
    ContestantTrack = apps.get_model("display", "ContestantTrack")

    duplicate_groups = list(
        ScoreLogEntry.objects.values(*IDEMPOTENCY_FIELDS).annotate(n=Count("id")).filter(n__gt=1)
    )

    if not duplicate_groups:
        return

    print(f"\n  Found {len(duplicate_groups)} duplicate ScoreLogEntry group(s) to clean up.")

    for group in duplicate_groups:
        group = dict(group)
        group.pop("n")
        matching = ScoreLogEntry.objects.filter(**group).order_by("pk")
        keep = matching.first()
        extras = list(matching.exclude(pk=keep.pk))
        if not extras:
            continue

        points_removed = sum(extra.points for extra in extras)
        contestant_id = group["contestant_id"]
        gate = group["gate"]

        print(
            f"  contestant={contestant_id} gate={gate!r} time={group['time']}: "
            f"removing {len(extras)} duplicate(s) (pks={[e.pk for e in extras]}), "
            f"correcting totals by {-points_removed:+.2f} points"
        )

        for extra in extras:
            extra.delete()

        if points_removed:
            GateCumulativeScore.objects.filter(contestant_id=contestant_id, gate=gate).update(
                points=F("points") - points_removed
            )
            ContestantTrack.objects.filter(contestant_id=contestant_id).update(
                score=F("score") - points_removed
            )


def noop_reverse(apps, schema_editor):
    # Deleted duplicate rows and the totals they inflated are not
    # reconstructible - this migration is intentionally one-directional.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0162_editableroute_updated_at"),
    ]

    operations = [
        migrations.RunPython(dedupe_score_log_entries, noop_reverse),
    ]
