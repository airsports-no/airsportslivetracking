"""
Cross-contest, platform-wide flight activity for the admin-only flight stats dashboard. Unlike
everything else in display.services, this deliberately ignores contest boundaries - it's an
operational view for site admins (calculator load, participation trends), not a contest-scoped
result.
"""

import datetime
from collections import defaultdict

from django.db.models import Case, CharField, Count, Value, When
from django.db.models.functions import TruncDay, TruncHour, TruncMonth, TruncWeek, TruncYear

from display.models import Contestant

STATUS_AWAITING_START = "awaiting_start"
STATUS_FLYING = "flying"
STATUS_FINISHED = "finished"

BIN_GRANULARITIES = {
    "hour": TruncHour,
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
    "year": TruncYear,
}


def build_admin_flight_stats(start: datetime.datetime, end: datetime.datetime, bin_granularity: str) -> dict:
    """
    Returns:
    - series: takeoff_time bucketed (in UTC - contestants span many contest timezones, so there's
      no single "local" time to bucket a platform-wide view in) by bin_granularity, split into
      awaiting_start/flying/finished by the contestant's current ContestantTrack state. Only
      contestants whose calculator has actually started are counted at all (a scheduled-but-never-
      tracked contestant was never really "flying").
    - unique_persons_per_day: distinct Person count (crew member1 and, when present, member2)
      across those same contestants, always bucketed by day regardless of bin_granularity - a
      finer/coarser breakdown of the same metric wouldn't mean anything different, so this isn't
      one of the selectable-bin series.
    """
    trunc_function = BIN_GRANULARITIES[bin_granularity]

    base_queryset = Contestant.objects.filter(
        contestanttrack__calculator_started=True,
        takeoff_time__gte=start,
        takeoff_time__lt=end,
    )

    status_counts = (
        base_queryset.annotate(bucket=trunc_function("takeoff_time", tzinfo=datetime.timezone.utc))
        .annotate(
            status=Case(
                When(contestanttrack__passed_finish_gate=True, then=Value(STATUS_FINISHED)),
                When(contestanttrack__passed_starting_gate=True, then=Value(STATUS_FLYING)),
                default=Value(STATUS_AWAITING_START),
                output_field=CharField(),
            )
        )
        .values("bucket", "status")
        .annotate(count=Count("id"))
    )

    buckets: dict[str, dict[str, int]] = {}
    for row in status_counts:
        bucket_key = row["bucket"].isoformat()
        buckets.setdefault(
            bucket_key, {STATUS_AWAITING_START: 0, STATUS_FLYING: 0, STATUS_FINISHED: 0}
        )
        buckets[bucket_key][row["status"]] = row["count"]

    series = [{"bucket_start": bucket_key, **counts} for bucket_key, counts in sorted(buckets.items())]

    persons_by_day: dict[datetime.date, set[int]] = defaultdict(set)
    for takeoff_time, member1_id, member2_id in base_queryset.values_list(
        "takeoff_time", "team__crew__member1_id", "team__crew__member2_id"
    ):
        day = takeoff_time.astimezone(datetime.timezone.utc).date()
        persons_by_day[day].add(member1_id)
        if member2_id is not None:
            persons_by_day[day].add(member2_id)

    unique_persons_per_day = [
        {"date": day.isoformat(), "count": len(person_ids)} for day, person_ids in sorted(persons_by_day.items())
    ]

    return {
        "bin": bin_granularity,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "series": series,
        "unique_persons_per_day": unique_persons_per_day,
    }
