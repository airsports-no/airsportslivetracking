"""
Push notifications to the Airsports mobile apps through Firebase Cloud Messaging, and the same flight notifications for
the MSFS client, which has no push: they are kept as ClientNotification rows that the client fetches while it runs.

Nothing is sent unless ``settings.PUSH_NOTIFICATIONS_ENABLED`` is true. FCM tokens that Google reports as dead are
deleted so we stop sending to them.
"""

import datetime
import logging
from typing import Iterable

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from display.models import ClientNotification, Contestant, MobileAppActivity, MobileDevice, Person, PushNotificationLog
from display.models.mobile_device import PLATFORM_MSFS
from display.services.received_positions import last_received_position_time
from display.utilities.tracking_definitions import (
    TRACKING_COPILOT,
    TRACKING_PILOT,
    TRACKING_PILOT_AND_COPILOT,
)

logger = logging.getLogger(__name__)

ANDROID_CHANNEL = "flight_reminders"


def _ensure_firebase_initialized() -> None:
    import firebase_admin

    try:
        firebase_admin.get_app()
    except ValueError:
        from display.auth_backends import FirebaseMigrationBackend

        FirebaseMigrationBackend()._initialize_firebase()


def _send_one(device: MobileDevice, title: str, body: str, data: dict[str, str]) -> bool:
    """Returns False when FCM says the token is no longer valid (the device row is deleted)."""
    from firebase_admin import messaging

    _ensure_firebase_initialized()
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


# A pilot who used the MSFS client this recently gets the flight notifications there too.
MSFS_CLIENT_ACTIVE_DAYS = 30
# How long the client can still fetch a notification (it shows only the ones that arrive while it runs).
CLIENT_NOTIFICATION_KEEP_DAYS = 7


def uses_msfs_client(person: Person, now: datetime.datetime = None) -> bool:
    """The person's MSFS client has talked to the server in the last MSFS_CLIENT_ACTIVE_DAYS."""
    now = now or timezone.now()
    return MobileAppActivity.objects.filter(
        platform=PLATFORM_MSFS,
        user__email__iexact=person.email,
        last_seen__gte=now - datetime.timedelta(days=MSFS_CLIENT_ACTIVE_DAYS),
    ).exists()


def _notify_once(
    kind: str,
    contestant: Contestant,
    person: Person,
    title: str,
    body: str,
    client_body: str = None,
    to_phone: bool = True,
    to_client: bool = True,
    now: datetime.datetime = None,
) -> bool:
    """
    Sends at most once per (kind, contestant, person): by push to the person's phones, and to the MSFS client's
    notifications when they use it ([client_body] instead of [body] there, for text about the phone). [to_phone] /
    [to_client] limit it to one of them. Returns True when something was sent.
    """
    phone = to_phone and person.mobile_devices.exists()
    client = to_client and uses_msfs_client(person, now)
    if not phone and not client:
        return False
    try:
        with transaction.atomic():
            log = PushNotificationLog.objects.create(kind=kind, contestant=contestant, person=person)
    except IntegrityError:
        return False  # already sent
    reached = 0
    if phone:
        reached += send_to_person(
            person,
            title,
            body,
            {"type": kind, "contestant_id": str(contestant.pk), "navigation_task_id": str(contestant.navigation_task_id)},
        )
    if client:
        ClientNotification.objects.create(
            person=person,
            kind=kind,
            title=title,
            body=client_body or body,
            contestant=contestant,
            navigation_task_id=contestant.navigation_task_id,
        )
        ClientNotification.objects.filter(
            person=person, created_at__lt=timezone.now() - datetime.timedelta(days=CLIENT_NOTIFICATION_KEEP_DAYS)
        ).delete()
        reached += 1
    if reached == 0:
        # Nothing got through (FCM error or only dead tokens): forget it so the next run can retry.
        log.delete()
        return False
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
                client_body=f"{contestant.navigation_task.name}: tracking opens in about {minutes} min. "
                "Have MSFS and the Air Sports client running, and press play to start tracking.",
                now=now,
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
                client_body=f"{contestant.navigation_task.name} has started but no positions have arrived. "
                "Make sure the Air Sports client is connected to MSFS and tracking is on (the play button).",
                now=now,
            ):
                sent += 1
    return sent


def notify_scoring_started(now: datetime.datetime = None) -> int:
    """
    'Scoring has started - your flight is being tracked' once the live calculator has been started by the first received
    position. This is the positive confirmation that the whole chain (phone, Traccar, processor, calculator) works.
    """
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0
    now = now or timezone.now()
    contestants = Contestant.objects.filter(
        finished_by_time__gt=now,
        tracking_device__in=(TRACKING_PILOT, TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT),
        contestanttrack__calculator_started=True,
        contestanttrack__calculator_finished=False,
    ).select_related("team__crew__member1", "team__crew__member2", "navigation_task")
    sent = 0
    for contestant in contestants:
        for person in _app_tracked_people(contestant):
            if _notify_once(
                PushNotificationLog.KIND_SCORING_STARTED,
                contestant,
                person,
                "Your flight is being scored",
                f"{contestant.navigation_task.name}: your positions are arriving and scoring has started. "
                "Everything is working.",
                now=now,
            ):
                sent += 1
    return sent


def notify_still_tracking(now: datetime.datetime = None) -> int:
    """
    'Your flight window closed N minutes ago and your phone is still sending positions': a phone left tracking after landing
    drains its battery and may keep recording. The same for the MSFS client left tracking (its simulator tracking id): that
    message goes to the client only, and the phone's only to the phone. Not sent when the pilot has another flight open or
    about to open (tracking through several flights is normal), and at most once per flight.
    """
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0
    now = now or timezone.now()
    grace = datetime.timedelta(minutes=settings.PUSH_STILL_TRACKING_GRACE_MINUTES)
    contestants = Contestant.objects.filter(
        finished_by_time__lte=now - grace,
        finished_by_time__gt=now - datetime.timedelta(hours=6),
        tracking_device__in=(TRACKING_PILOT, TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT),
    ).select_related("team__crew__member1", "team__crew__member2", "navigation_task")
    sent = 0
    for contestant in contestants:
        for person in _app_tracked_people(contestant):
            phone_sending = _still_sending(person.app_tracking_id, now)
            simulator_sending = _still_sending(person.simulator_tracking_id, now)
            if not phone_sending and not simulator_sending:
                continue  # both have stopped sending
            if _has_flight_open_or_soon(person, now):
                continue
            minutes = int((now - contestant.finished_by_time).total_seconds() // 60)
            closed = f"The tracking window for {contestant.navigation_task.name} closed {minutes} minutes ago, but "
            if _notify_once(
                PushNotificationLog.KIND_STILL_TRACKING,
                contestant,
                person,
                "Tracking is still on",
                closed + "your phone is still sending positions. Open Airsports and stop tracking if you have landed.",
                client_body=closed + "the Air Sports client is still sending positions from the simulator. "
                "Stop tracking in the client if you have landed.",
                to_phone=phone_sending,
                to_client=simulator_sending,
                now=now,
            ):
                sent += 1
    return sent


def _still_sending(device: str, now: datetime.datetime) -> bool:
    """Positions from [device] arrived in the last two minutes."""
    heard = last_received_position_time(device) if device else None
    return heard is not None and heard >= now - datetime.timedelta(minutes=2)


def _has_flight_open_or_soon(person: Person, now: datetime.datetime) -> bool:
    """Another flight of this person is open now or opens within the hour."""
    return Contestant.objects.filter(
        Q(team__crew__member1=person) | Q(team__crew__member2=person),
        tracker_start_time__lte=now + datetime.timedelta(hours=1),
        finished_by_time__gt=now,
    ).exists()


def notify_flight_scored(now: datetime.datetime = None) -> int:
    """
    'Live scoring has finished: N points' once the calculator has finished and the results can be seen. The calculator
    processes positions ``calculation_delay_minutes`` late and scores are held back on the map for that long, so the message
    waits until the finish time plus that delay, plus a short settling time for the last scoring (the photo observations the
    crew never marked are scored just after the calculator finishes). Only to people who may see the results (the same rule
    as the live map), and only for recent flights.
    """
    if not settings.PUSH_NOTIFICATIONS_ENABLED:
        return 0
    from display.models import MyUser
    from display.services.map_access import can_view_task_map

    now = now or timezone.now()
    settle = datetime.timedelta(minutes=settings.PUSH_FLIGHT_SCORED_SETTLE_MINUTES)
    contestants = Contestant.objects.filter(
        contestanttrack__calculator_finished=True,
        finished_by_time__gt=now - datetime.timedelta(hours=24),
        tracking_device__in=(TRACKING_PILOT, TRACKING_COPILOT, TRACKING_PILOT_AND_COPILOT),
    ).select_related("team__crew__member1", "team__crew__member2", "navigation_task__contest", "contestanttrack")
    sent = 0
    for contestant in contestants:
        task = contestant.navigation_task
        released_at = contestant.finished_by_time + datetime.timedelta(minutes=task.calculation_delay_minutes) + settle
        if now < released_at:
            continue  # the organizer still holds the scores back (or the last scoring has not settled)
        for person in _app_tracked_people(contestant):
            if not person.mobile_devices.exists() and not uses_msfs_client(person, now):
                continue
            user = MyUser.objects.filter(email=person.email).first()
            if not can_view_task_map(user, task):
                continue
            points = contestant.contestanttrack.score
            if _notify_once(
                PushNotificationLog.KIND_FLIGHT_SCORED,
                contestant,
                person,
                "Live scoring has finished",
                f"{task.name}: {points:g} points. The organizers can still adjust the result.",
                now=now,
            ):
                sent += 1
    return sent
