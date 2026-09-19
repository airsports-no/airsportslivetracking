"""
Platform-wide utilization statistics for the admin dashboard - country breakdown, activity over
time, task-type popularity, and team/pilot retention ("is this platform sticky"). Companion to
admin_flight_stats.py/admin_upcoming_contestants.py (same cross-contest, admin-only scope).

Country data deliberately reads NavigationTask._nominatim directly rather than the
country_code/country_name properties, which lazily trigger a live (rate-limited) Nominatim
lookup on a cache miss - fine for rendering one task's detail page, not for an aggregate query
across every task on the platform. A task with no cached geocode yet is grouped as "Unknown"
here rather than triggering one. display.utilities.statistics_utilities.get_system_statistics
already established this same safe pattern for the legacy Django statistics page; this module
is a separate, JSON-API-shaped set of queries rather than a change to that function, so as not
to alter its template's existing data contract.
"""

import datetime
from collections import Counter, defaultdict

from django.db.models import Count
from django.db.models.functions import TruncDay, TruncHour, TruncMonth, TruncWeek, TruncYear

from display.models import Contest, Contestant, NavigationTask, Person, Team

ACTIVITY_BIN_GRANULARITIES = {
    "hour": TruncHour,
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
    "year": TruncYear,
}

TEAM_CONTEST_COUNT_OVERFLOW_LABEL = "5+"


def get_country_stats() -> list[dict]:
    """
    Navigation tasks / contests / contestants per country, keyed by the cached Nominatim
    reverse-geocode result (ISO alpha-2 country_code plus a display name).
    """
    task_rows = NavigationTask.objects.annotate(contestant_count=Count("contestant")).values(
        "pk", "contest_id", "_nominatim", "contestant_count"
    )

    by_country: dict[str, dict] = {}
    for row in task_rows:
        nominatim = row["_nominatim"] or {}
        address = nominatim.get("address", {})
        country_code = (address.get("country_code") or "").upper()
        country_name = address.get("country") or "Unknown"
        key = country_code or f"unknown:{country_name}"

        entry = by_country.setdefault(
            key,
            {"country_code": country_code, "country_name": country_name, "tasks": 0, "contest_ids": set(), "contestants": 0},
        )
        entry["tasks"] += 1
        entry["contestants"] += row["contestant_count"]
        if row["contest_id"] is not None:
            entry["contest_ids"].add(row["contest_id"])

    result = [
        {
            "country_code": entry["country_code"],
            "country_name": entry["country_name"],
            "contests": len(entry["contest_ids"]),
            "tasks": entry["tasks"],
            "contestants": entry["contestants"],
        }
        for entry in by_country.values()
    ]
    result.sort(key=lambda row: row["tasks"], reverse=True)
    return result


def get_activity_over_time(start: datetime.datetime, end: datetime.datetime, bin_granularity: str) -> dict:
    """
    Contests and navigation tasks bucketed by Contest.start_time/NavigationTask.start_time (in
    UTC, for the same cross-timezone reason admin_flight_stats.py bucketizes takeoff_time in
    UTC). Neither model has a creation timestamp, so start_time - when the event actually
    happened - is the closest available measure of platform activity over time.
    """
    trunc_function = ACTIVITY_BIN_GRANULARITIES[bin_granularity]

    contest_counts = (
        Contest.objects.filter(start_time__gte=start, start_time__lt=end)
        .annotate(bucket=trunc_function("start_time", tzinfo=datetime.timezone.utc))
        .values("bucket")
        .annotate(count=Count("id"))
    )
    task_counts = (
        NavigationTask.objects.filter(start_time__gte=start, start_time__lt=end)
        .annotate(bucket=trunc_function("start_time", tzinfo=datetime.timezone.utc))
        .values("bucket")
        .annotate(count=Count("id"))
    )

    buckets: dict[str, dict[str, int]] = {}
    for row in contest_counts:
        buckets.setdefault(row["bucket"].isoformat(), {"contests": 0, "tasks": 0})["contests"] = row["count"]
    for row in task_counts:
        buckets.setdefault(row["bucket"].isoformat(), {"contests": 0, "tasks": 0})["tasks"] = row["count"]

    series = [{"bucket_start": bucket_key, **counts} for bucket_key, counts in sorted(buckets.items())]
    return {"bin": bin_granularity, "start": start.isoformat(), "end": end.isoformat(), "series": series}


def get_task_type_popularity() -> list[dict]:
    """Navigation task count grouped by task_subtype - which CIMA/legacy task types actually get used."""
    counts = (
        NavigationTask.objects.values("task_subtype")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    return [
        {"task_subtype": row["task_subtype"] or "unspecified", "count": row["count"]}
        for row in counts
    ]


def get_retention_stats() -> dict:
    """
    Team- and person-level repeat participation, as a "is this platform sticky" proxy: what
    fraction of teams/pilots come back for more than one contest, and what does the
    contests-per-team distribution look like (a chart, not just one percentage, since "60%
    return" reads very differently as "everyone flies exactly twice" vs. "a long tail of
    regulars carries a mostly one-and-done crowd").
    """
    team_contest_counts = list(
        Team.objects.annotate(contest_count=Count("contestant__navigation_task__contest", distinct=True))
        .filter(contest_count__gt=0)
        .values_list("contest_count", flat=True)
    )
    team_stats = _summarize_repeat_participation(team_contest_counts)

    person_to_contests: dict[int, set[int]] = defaultdict(set)
    for member1_id, member2_id, contest_id in Contestant.objects.values_list(
        "team__crew__member1_id", "team__crew__member2_id", "navigation_task__contest_id"
    ):
        if member1_id is not None:
            person_to_contests[member1_id].add(contest_id)
        if member2_id is not None:
            person_to_contests[member2_id].add(contest_id)
    person_contest_counts = [len(contests) for contests in person_to_contests.values()]
    person_stats = _summarize_repeat_participation(person_contest_counts)

    return {
        "teams": team_stats,
        "persons": person_stats,
        "total_persons_ever_tracked": Person.objects.count(),
    }


def _summarize_repeat_participation(contest_counts: list[int]) -> dict:
    total = len(contest_counts)
    returning = sum(1 for count in contest_counts if count > 1)
    distribution = Counter(contest_counts)

    overflow = sum(count for value, count in distribution.items() if value >= 5)
    buckets = [{"contests": value, "count": count} for value, count in sorted(distribution.items()) if value < 5]
    if overflow:
        buckets.append({"contests": TEAM_CONTEST_COUNT_OVERFLOW_LABEL, "count": overflow})

    return {
        "total": total,
        "returning": returning,
        "returning_pct": round(100 * returning / total, 1) if total else 0.0,
        "distribution": buckets,
    }
