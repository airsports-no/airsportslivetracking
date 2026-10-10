"""
Push notifications to the Airsports mobile apps through Firebase Cloud Messaging.

Nothing is sent unless ``settings.PUSH_NOTIFICATIONS_ENABLED`` is true. FCM tokens that Google reports as dead are
deleted so we stop sending to them.
"""

import datetime
import logging
from typing import Iterable

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from display.models import Contestant, MobileDevice, Person, PushNotificationLog
from display.utilities.tracking_definitions import (
    TRACKING_COPILOT,
    TRACKING_PILOT,
    TRACKING_PILOT_AND_COPILOT,
)

logger = logging.getLogger(__name__)

ANDROID_CHANNEL = "flight_reminders"


def _send_one(device: MobileDevice, title: str, body: str, data: dict[str, str]) -> bool:
    """Returns False when FCM says the token is no longer valid (the device row is deleted)."""
    from firebase_admin import messaging

    from display.auth_backends import FirebaseMigrationBackend

    FirebaseMigrationBackend()._initialize_firebase()
    message = messaging.Message(
        token=device.push_token,
        notification=messaging.Notification(title=title, body=body),
        data={k: str(v) for k, v in data.items()},
        android=messaging.AndroidConfig(
            priority="high", notification=messaging.AndroidNotification(channel_id=ANDROID_CHANNEL)
        ),
        apns=messaging.APNSConfig(headers={"apns-priority": "10"}),
    )
    try:
        messaging.send(message)
        return True
    except (messaging.UnregisteredError, messaging.SenderIdMismatchError):
        logger.info("Deleting dead push token for %s", device)
        device.delete()
        return False


def send_to_person(person: Person, title: str, body: str, data: dict[str, str]) -> int:
    """Sends to every registered device of the person; returns how many devices were reached."""
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0
    reached = 0
    for device in list(person.mobile_devices.all()):
        try:
            if _send_one(device, title, body, data):
                reached += 1
        except Exception:
            logger.exception("Failed sending push notification to %s", device)
    return reached


def _app_tracked_people(contestant: Contestant) -> list[Person]:
    """The people whose phones are supposed to track this contestant."""
    crew = contestant.team.crew
    if contestant.tracking_device == TRACKING_PILOT:
        return [crew.member1]
    if contestant.tracking_device == TRACKING_COPILOT:
        return [crew.member2] if crew.member2 else []
    if contestant.tracking_device == TRACKING_PILOT_AND_COPILOT:
        return [p for p in (crew.member1, crew.member2) if p]
    return []  # hardware tracker: nothing for the phone to do


def _notify_once(kind: str, contestant: Contestant, person: Person, title: str, body: str) -> bool:
    """Sends at most once per (kind, contestant, person). Returns True when something was sent."""
    if not person.mobile_devices.exists():
        return False
    try:
        with transaction.atomic():
            log = PushNotificationLog.objects.create(kind=kind, contestant=contestant, person=person)
    except IntegrityError:
        return False  # already sent
    reached = send_to_person(
        person,
        title,
        body,
        {"type": kind, "contestant_id": str(contestant.pk), "navigation_task_id": str(contestant.navigation_task_id)},
    )
    log.devices_reached = reached
    log.save(update_fields=["devices_reached"])
    return True


def notify_upcoming_tracking_windows(now: datetime.datetime = None) -> int:
    """'Tracking opens in N minutes - open the app and start tracking' for contestants about to start."""
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0
    now = now or timezone.now()
    lead = datetime.timedelta(minutes=settings.PUSH_TRACKING_WINDOW_LEAD_MINUTES)
    contestants = Contestant.objects.filter(
        tracker_start_time__gt=now,
        tracker_start_time__lte=now + lead,
        tracking_device__in=(TRACKING_PILOT, TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT),
    ).select_related("team__crew__member1", "team__crew__member2", "navigation_task")
    sent = 0
    for contestant in contestants:
        minutes = max(1, round((contestant.tracker_start_time - now).total_seconds() / 60))
        for person in _app_tracked_people(contestant):
            if _notify_once(
                PushNotificationLog.KIND_TRACKING_WINDOW_OPENS,
                contestant,
                person,
                "Tracking opens soon",
                f"{contestant.navigation_task.name}: tracking opens in about {minutes} min. "
                "Open Airsports and tap Start tracking.",
            ):
                sent += 1
    return sent


def notify_not_tracking(now: datetime.datetime = None) -> int:
    """'Your flight has started but we receive no positions' a few minutes after take-off."""
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0
    now = now or timezone.now()
    grace = datetime.timedelta(minutes=settings.PUSH_NOT_TRACKING_GRACE_MINUTES)
    contestants = Contestant.objects.filter(
        takeoff_time__lte=now - grace,
        finished_by_time__gt=now,
        tracking_device__in=(TRACKING_PILOT, TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT),
        contestantreceivedposition__isnull=True,
    ).select_related("team__crew__member1", "team__crew__member2", "navigation_task").distinct()
    sent = 0
    for contestant in contestants:
        for person in _app_tracked_people(contestant):
            if _notify_once(
                PushNotificationLog.KIND_NOT_TRACKING,
                contestant,
                person,
                "We are not receiving your position",
                f"{contestant.navigation_task.name} has started but no positions have arrived. "
                "Open Airsports and make sure tracking is on.",
            ):
                sent += 1
    return sent
