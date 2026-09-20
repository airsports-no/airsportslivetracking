"""
Cross-contest, platform-wide flight activity for the admin-only flight stats dashboard. Unlike
everything else in display.services, this deliberately ignores contest boundaries - it's an
operational view for site admins (calculator load, participation trends), not a contest-scoped
result.
"""

import datetime
from collections import defaultdict

from django.db.models import Case, CharField, Count, Q, Value, When
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
    Returns, both bucketed by the same bin_granularity (in UTC - contestants span many contest
    timezones, so there's no single "local" time to bucket a platform-wide view in):
    - series: takeoff_time split into awaiting_start/flying/finished by the contestant's current
      ContestantTrack state, treating anyone past their own finished_by_time as finished even if
      the calculator never explicitly marked them so (see the Case comment below - current_state
      is a live-calculator-only field that just stops updating, it isn't retroactively
      corrected). Only contestants whose calculator has actually started are counted at all (a
      scheduled-but-never-tracked contestant was never really "flying").
    - unique_persons_series: distinct Person count (crew member1 and, when present, member2)
      across those same contestants, per bucket.
    """
    trunc_function = BIN_GRANULARITIES[bin_granularity]

    bucketed_queryset = Contestant.objects.filter(
        contestanttrack__calculator_started=True,
        takeoff_time__gte=start,
        takeoff_time__lt=end,
    ).annotate(bucket=trunc_function("takeoff_time", tzinfo=datetime.timezone.utc))

    status_counts = (
        bucketed_queryset.annotate(
            status=Case(
                # A contestant whose scheduled window is over counts as finished regardless of
                # whether the calculator ever cleanly reached that state itself (crash, timeout,
                # a task with no real finish gate, ...) - current_state is free-text set by the
                # live calculator and simply never updates again once it stops running, so
                # without this a contestant who, say, went off-track and was never resolved
                # would show as "flying" forever, including weeks after their contest ended.
                When(Q(contestanttrack__passed_finish_gate=True) | Q(finished_by_time__lt=end), then=Value(STATUS_FINISHED)),
                # Not contestanttrack__passed_starting_gate: until this session, nothing ever
                # set it (the StartingLinePassedEvent handler never called the equivalent of
                # passed_finishpoint()'s set_passed_finish_gate() - see orchestrator.py), so
                # every contestant that has ever started this task existed with it False. Now
                # fixed going forward, but that leaves it permanently False for everything
                # processed before the fix - current_state is the one field that's always been
                # correctly maintained (updates_current_state, called throughout the live
                # calculators) for "has this contestant's calculator actually progressed past
                # its initial waiting state."
                When(~Q(contestanttrack__current_state="Waiting..."), then=Value(STATUS_FLYING)),
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

    persons_by_bucket: dict[datetime.datetime, set[int]] = defaultdict(set)
    for bucket, member1_id, member2_id in bucketed_queryset.values_list(
        "bucket", "team__crew__member1_id", "team__crew__member2_id"
    ):
        persons_by_bucket[bucket].add(member1_id)
        if member2_id is not None:
            persons_by_bucket[bucket].add(member2_id)

    unique_persons_series = [
        {"bucket_start": bucket.isoformat(), "count": len(person_ids)}
        for bucket, person_ids in sorted(persons_by_bucket.items())
    ]

    return {
        "bin": bin_granularity,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "series": series,
        "unique_persons_series": unique_persons_series,
    }
