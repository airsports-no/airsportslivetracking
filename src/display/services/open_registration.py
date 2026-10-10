"""
Navigation tasks that a pilot can still register a flight for today ("self registration"), for the page that helps a
pilot find where to register before flying.
"""

import datetime
from typing import Optional

import pytz
from django.db.models import Q
from django.utils import timezone
from guardian.shortcuts import get_objects_for_user

from display.models import Contest, NavigationTask


def _day_bounds(now: datetime.datetime, timezone_name: Optional[str]):
    try:
        tz = pytz.timezone(timezone_name) if timezone_name else pytz.utc
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc
    local = now.astimezone(tz)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + datetime.timedelta(days=1)


def open_registration_tasks_today(
    timezone_name: Optional[str] = None, now: Optional[datetime.datetime] = None, user=None
):
    """
    Tasks that allow self registration and are not over yet, whose time window reaches into "today" (the calendar day
    in ``timezone_name``, default UTC). Public tasks of public contests are listed for everybody; a signed-in ``user``
    also gets the tasks of private contests (or private tasks) they may view, e.g. their own as an organizer. Sorted by
    contest, then start time.
    """
    now = now or timezone.now()
    _, end_of_day = _day_bounds(now, timezone_name)
    visible = Q(is_public=True, contest__is_public=True)
    if user is not None and user.is_authenticated:
        viewable = get_objects_for_user(user, "display.view_contest", klass=Contest, accept_global_perms=False)
        visible |= Q(contest__in=viewable.values("pk"))
    return (
        NavigationTask.objects.filter(
            visible,
            allow_self_management=True,
            start_time__lt=end_of_day,
            finish_time__gte=now,
        )
        .select_related("contest")
        .order_by("contest__name", "start_time")
    )


def describe(task: NavigationTask, now: datetime.datetime) -> dict:
    contest = task.contest
    has_location = bool(contest.location) and (contest.latitude != 0.0 or contest.longitude != 0.0)
    return {
        "contest_id": contest.pk,
        "contest_name": contest.name,
        "country": str(contest.country) if contest.country else "",
        "time_zone": str(contest.time_zone),
        "latitude": contest.latitude if has_location else None,
        "longitude": contest.longitude if has_location else None,
        "navigation_task_id": task.pk,
        "navigation_task_name": task.name,
        "start_time": task.start_time,
        "finish_time": task.finish_time,
        "is_open_now": task.start_time <= now <= task.finish_time,
    }
