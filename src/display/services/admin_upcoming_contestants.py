"""
Cross-contest, forward-looking contestant schedule for the admin-only "what's coming up" view -
lets a site admin see expected flying activity over the next few days/weeks at a glance. The
human-facing counterpart to calculator_pool_scaler.py's own forward-looking
tracker_start_time__lte=horizon query, which pre-warms the live-calculator pool for the same
reason (see CLAUDE.md's "Live calculators" section).
"""

import datetime

from display.models import Contestant


def get_upcoming_contestants(days: int) -> list[dict]:
    now = datetime.datetime.now(datetime.timezone.utc)
    horizon = now + datetime.timedelta(days=days)

    contestants = (
        Contestant.objects.filter(takeoff_time__gte=now, takeoff_time__lt=horizon)
        .select_related("navigation_task__contest", "team__crew__member1", "team__crew__member2", "team__aeroplane")
        .order_by("takeoff_time")
    )

    return [
        {
            "id": contestant.pk,
            "contest_id": contestant.navigation_task.contest_id,
            "contest_name": contestant.navigation_task.contest.name,
            "navigation_task_id": contestant.navigation_task_id,
            "navigation_task_name": contestant.navigation_task.name,
            "team": str(contestant.team.crew),
            "aeroplane": contestant.team.aeroplane.registration,
            "takeoff_time": contestant.takeoff_time.isoformat(),
            "contest_time_zone": str(contestant.navigation_task.contest.time_zone),
        }
        for contestant in contestants
    ]
