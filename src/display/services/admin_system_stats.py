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

from django.db import connection
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDay, TruncHour, TruncMonth, TruncWeek, TruncYear
from django_countries import countries

from display.models import (
    ANOMALY,
    Aeroplane,
    Club,
    Contest,
    Contestant,
    ContestantReceivedPosition,
    NavigationTask,
    Person,
    ScoreLogEntry,
    Team,
)

ACTIVITY_BIN_GRANULARITIES = {
    "hour": TruncHour,
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
    "year": TruncYear,
}

TEAM_CONTEST_COUNT_CEILING = 5


def _approximate_row_count(model) -> int:
    """
    ContestantReceivedPosition alone is 11M+ rows (every GPS ping ever recorded) and growing -
    an exact COUNT(*) took ~2.5s in local testing and only gets slower, which is not something to
    run on every admin dashboard load just to show a "scale of the platform" headline number.
    information_schema.tables.table_rows is an InnoDB estimate (refreshed periodically by MySQL,
    not on every write) rather than an exact count, which is a fine trade for this use - falls
    back to an exact count on a non-MySQL backend (e.g. a future test DB swap) where that table
    doesn't exist.
    """
    if connection.vendor != "mysql":
        return model.objects.count()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_rows FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
            [model._meta.db_table],
        )
        row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def get_overview_stats() -> dict:
    """
    Headline scale/funnel numbers and top lists - the "impressive numbers for a marketing deck"
    view, plus enough funnel detail (started -> crossed start) to sanity-check them. Mirrors
    display.utilities.statistics_utilities.get_system_statistics's metric selection (the legacy
    Django statistics page this is replacing) but is its own query set, not a call into that
    function, so the legacy page's template contract is unaffected until it's deleted outright.
    """
    started_qs = Contestant.objects.filter(contestanttrack__calculator_started=True)
    # Not contestanttrack__passed_starting_gate: until this session nothing ever set it (see the
    # comment in admin_flight_stats.py's build_admin_flight_stats), so it's permanently False for
    # every contestant processed before that fix. current_state has always been correctly
    # maintained by the live calculators.
    crossed_starting_qs = started_qs.exclude(contestanttrack__current_state="Waiting...")
    country_rows = get_country_stats()

    return {
        "number_of_persons": Person.objects.count(),
        "number_of_contests": Contest.objects.count(),
        "number_of_tasks": NavigationTask.objects.count(),
        "number_of_contestants": Contestant.objects.count(),
        "number_of_countries_reached": len([row for row in country_rows if row["country_code"]]),
        "total_gps_positions": _approximate_row_count(ContestantReceivedPosition),
        "total_anomalies": ScoreLogEntry.objects.filter(type=ANOMALY).count(),
        "average_air_speed": Contestant.objects.aggregate(value=Avg("air_speed"))["value"] or 0,
        "number_of_started_contestants": started_qs.count(),
        "number_of_contestants_crossed_starting": crossed_starting_qs.count(),
        "number_of_persons_crossed_starting": Person.objects.filter(
            Q(crewmember_one__team__contestant__in=crossed_starting_qs)
            | Q(crewmember_two__team__contestant__in=crossed_starting_qs)
        )
        .distinct()
        .count(),
        "top_clubs": list(
            Club.objects.values("name").annotate(count=Count("team")).order_by("-count").filter(count__gt=0)[:5]
        ),
        "top_aircraft_types": list(
            Aeroplane.objects.exclude(type="").values("type").annotate(count=Count("id")).order_by("-count")[:5]
        ),
    }


def get_country_stats() -> list[dict]:
    """
    Navigation tasks / contests / contestants per country, keyed by the cached Nominatim
    reverse-geocode result (ISO alpha-2 country_code), plus a representative latitude/longitude
    (the average of every task's own geocoded point in that country) for plotting a bubble on a
    map - deliberately not a static country-centroid table: this is a real, data-derived "where
    our tasks actually are" point rather than an arbitrary reference point that could land
    somewhere with no tasks anywhere near it for a large/irregular country.
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
            {
                "country_code": country_code,
                "country_name": country_name,
                "tasks": 0,
                "contest_ids": set(),
                "contestants": 0,
                "coordinate_sum": [0.0, 0.0],
                "coordinate_count": 0,
            },
        )
        entry["tasks"] += 1
        entry["contestants"] += row["contestant_count"]
        if row["contest_id"] is not None:
            entry["contest_ids"].add(row["contest_id"])
        try:
            lat, lon = float(nominatim["lat"]), float(nominatim["lon"])
        except (KeyError, TypeError, ValueError):
            pass
        else:
            entry["coordinate_sum"][0] += lat
            entry["coordinate_sum"][1] += lon
            entry["coordinate_count"] += 1

    result = []
    for entry in by_country.values():
        # Nominatim's own "country" address field is in whichever language matches the queried
        # location (e.g. "Norge" for a Norwegian point, not "Norway") - prefer the ISO code's
        # English name when there is one, since a country breakdown mixing languages by chance of
        # which country's data happened to resolve first reads as a bug.
        display_name = countries.name(entry["country_code"]) if entry["country_code"] else ""
        coordinate_count = entry["coordinate_count"]
        result.append(
            {
                "country_code": entry["country_code"],
                "country_name": display_name or entry["country_name"],
                "contests": len(entry["contest_ids"]),
                "tasks": entry["tasks"],
                "contestants": entry["contestants"],
                "latitude": entry["coordinate_sum"][0] / coordinate_count if coordinate_count else None,
                "longitude": entry["coordinate_sum"][1] / coordinate_count if coordinate_count else None,
            }
        )
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
    """
    Navigation task count grouped by effective_task_subtype - which CIMA/legacy task types
    actually get used. Grouping on the raw task_subtype column would be wrong: a blank value
    there doesn't mean "no known type," it means "use this task's scorecard family's legacy
    default" (NavigationTask.effective_task_subtype) - every legacy task on a given scorecard
    family is really one category, not a generic "unspecified" bucket, and NULL vs "" being
    distinct raw values would even split that non-category into two.
    """
    counts = Counter(
        task.effective_task_subtype or "unspecified"
        for task in NavigationTask.objects.select_related("scorecard", "original_scorecard")
    )
    return [
        {"task_subtype": subtype, "count": count}
        for subtype, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
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
    """
    Cumulative ("attended at least N contests") rather than an exact-count histogram - the usual
    convention for a retention curve (every product/growth analytics tool presents it this way):
    a monotonically decreasing "N+" series answers "how many are still engaged at each depth"
    directly, where an exact-count histogram needs the reader to sum tails themselves.
    """
    total = len(contest_counts)
    returning = sum(1 for count in contest_counts if count > 1)

    distribution = []
    for n in range(1, TEAM_CONTEST_COUNT_CEILING + 1):
        at_least_n = sum(1 for count in contest_counts if count >= n)
        if at_least_n == 0:
            break
        label = f"{n}+" if n == TEAM_CONTEST_COUNT_CEILING else str(n)
        distribution.append({"contests": label, "count": at_least_n})

    return {
        "total": total,
        "returning": returning,
        "returning_pct": round(100 * returning / total, 1) if total else 0.0,
        "distribution": distribution,
    }
