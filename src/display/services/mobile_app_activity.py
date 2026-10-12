"""Which mobile apps (and which versions) have recently talked to the server, for the admin statistics."""

import datetime
from typing import Optional

from django.core.cache import cache
from django.utils import timezone

from display.models import MobileAppActivity, Person
from display.models.mobile_device import PLATFORM_ANDROID, PLATFORM_IOS
from display.services.received_positions import last_received_coordinates

PLATFORM_HEADER = "HTTP_X_APP_PLATFORM"
VERSION_HEADER = "HTTP_X_APP_VERSION"
BUILD_HEADER = "HTTP_X_APP_BUILD"

# A user's row is written at most this often, however many requests the app makes (it polls while tracking).
WRITE_INTERVAL_SECONDS = 60


def record_app_activity(request) -> bool:
    """
    Notes that the signed-in user's app just made a request, from the headers the apps send (X-App-Platform, X-App-Version,
    X-App-Build). Does nothing for other clients, anonymous users, or when it has already been noted this minute.
    Returns True when a row was written.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    platform = request.META.get(PLATFORM_HEADER, "").strip().lower()
    if platform not in (PLATFORM_ANDROID, PLATFORM_IOS):
        return False
    version = request.META.get(VERSION_HEADER, "").strip()[:40]
    build = request.META.get(BUILD_HEADER, "").strip()[:20]
    # Also when the version changes: an update shows up at once, not a minute later.
    key = f"mobile_app_activity:{user.pk}:{platform}:{version}:{build}"
    if not cache.add(key, 1, WRITE_INTERVAL_SECONDS):
        return False
    now = timezone.now()
    MobileAppActivity.objects.update_or_create(
        user=user, platform=platform, defaults={"app_version": version, "app_build": build, "last_seen": now}
    )
    return True


def connected_apps(minutes: int, now: Optional[datetime.datetime] = None) -> dict:
    """The apps seen in the last [minutes], newest first, with a count per version."""
    now = now or timezone.now()
    rows = list(
        MobileAppActivity.objects.filter(last_seen__gte=now - datetime.timedelta(minutes=minutes))
        .select_related("user")
        .order_by("-last_seen")
    )
    # The last position the tracking stream delivered for each person's phone (nothing is sent by the app for this).
    people = {p.email.lower(): p for p in Person.objects.filter(email__in=[row.user.email for row in rows])}
    by_version: dict[tuple, int] = {}
    for row in rows:
        key = (row.platform, row.app_version, row.app_build)
        by_version[key] = by_version.get(key, 0) + 1
    return {
        "window_minutes": minutes,
        "total": len(rows),
        "by_version": [
            {"platform": platform, "app_version": version, "app_build": build, "users": count}
            for (platform, version, build), count in sorted(by_version.items(), key=lambda item: -item[1])
        ],
        "users": [
            {
                "name": (f"{row.user.first_name} {row.user.last_name}").strip(),
                "email": row.user.email,
                "platform": row.platform,
                "app_version": row.app_version,
                "app_build": row.app_build,
                "last_seen": row.last_seen,
                "position": _position_of(people.get((row.user.email or "").lower())),
            }
            for row in rows
        ],
    }


def _position_of(person: Optional[Person]) -> Optional[dict]:
    """Where the person's phone last reported from, with the time of that report; None when no position is known."""
    coordinates = last_received_coordinates(person.app_tracking_id) if person else None
    if not coordinates:
        return None
    return {"latitude": coordinates["latitude"], "longitude": coordinates["longitude"], "time": coordinates["time"]}
