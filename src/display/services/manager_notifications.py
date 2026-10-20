"""
E-mails to the managers of a contest when a contestant starts or finishes a navigation task (GitHub #17), for cups where
contestants fly a task on their own at different times and the organisers want to know when results come in. Each task
turns them on with NavigationTask.notify_managers_on_start / notify_managers_on_finish.

The hooks are ContestantTrack.set_calculator_started and set_calculator_finished. A calculator also starts again when a track
is recalculated, so a notification is only sent while the flight is live (before its tracking window has ended, or shortly
after for the finish), and at most once per contestant: an old flight that is recalculated sends nothing.
"""

import datetime
import logging

import html2text
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.template import Context, Template
from guardian.shortcuts import get_users_with_perms

from display.models import Contestant
from display.templatetags.frontend_urls import fe_url
from display.utilities.email_templates import CONTESTANT_FINISHED_EMAIL, CONTESTANT_STARTED_EMAIL, EMAIL_SIGNATURE
from display.utilities.welcome_emails import FOOTER, HEADER

logger = logging.getLogger(__name__)

APP_URL = "https://app.airsports.no"

STARTED = "started"
FINISHED = "finished"

# How long after the end of the tracking window a finish still counts as live (the calculator may wind down a bit late)
FINISH_GRACE = datetime.timedelta(hours=2)
# How long a sent notification is remembered, so a restarted calculator does not send it again
SENT_MEMORY_SECONDS = 7 * 24 * 3600
# The finish e-mail waits a little so the last scores of the flight have been written
FINISH_DELAY_SECONDS = 60


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _wanted(contestant: Contestant, kind: str) -> bool:
    task = contestant.navigation_task
    return task.notify_managers_on_start if kind == STARTED else task.notify_managers_on_finish


def _is_live(contestant: Contestant, kind: str) -> bool:
    end = contestant.finished_by_time
    if end is None:
        return False
    return _now() <= (end if kind == STARTED else end + FINISH_GRACE)


def _sent_key(contestant: Contestant, kind: str) -> str:
    return f"manager_notification:{kind}:{contestant.pk}"


def queue_manager_notification(contestant: Contestant, kind: str) -> bool:
    """
    Called from the calculator: queue the e-mail if the task wants it, the flight is live and it has not been sent before.
    Never raises, a notification must not disturb scoring. Returns whether an e-mail was queued.
    """
    try:
        if not _wanted(contestant, kind) or not _is_live(contestant, kind):
            return False
        # cache.add is atomic, so two calculators racing for the same contestant queue one e-mail
        if not cache.add(_sent_key(contestant, kind), True, SENT_MEMORY_SECONDS):
            return False
        from display.tasks import send_manager_notification_task

        countdown = FINISH_DELAY_SECONDS if kind == FINISHED else 0
        pk = contestant.pk
        transaction.on_commit(lambda: send_manager_notification_task.apply_async((pk, kind), countdown=countdown))
        return True
    except Exception:
        logger.exception("Failed queueing the %s notification for contestant %s", kind, contestant.pk)
        return False


def recipients(contestant: Contestant) -> list[str]:
    """The addresses of the people who manage the contest, except the crew of the flight itself."""
    contest = contestant.navigation_task.contest
    managers = get_users_with_perms(
        contest, only_with_perms_in=["change_contest"], with_superusers=False, with_group_users=True
    )
    crew = contestant.team.crew
    crew_emails = {(person.email or "").strip().lower() for person in (crew.member1, crew.member2) if person}
    addresses = set()
    for user in managers:
        email = (user.email or "").strip().lower()
        if email and email not in crew_emails and user.is_active:
            addresses.add(email)
    return sorted(addresses)


def _crew_name(contestant: Contestant) -> str:
    crew = contestant.team.crew
    names = [f"{person.first_name} {person.last_name}".strip() for person in (crew.member1, crew.member2) if person]
    return " and ".join(name for name in names if name) or str(contestant.team)


def _format_time(contestant: Contestant, moment) -> str:
    if moment is None:
        return ""
    return moment.astimezone(contestant.navigation_task.contest.time_zone).strftime("%Y-%m-%d %H:%M %Z")


def send_manager_notification(contestant: Contestant, kind: str) -> int:
    """Mail the managers of the contest about [contestant]. Returns the number of recipients."""
    addresses = recipients(contestant)
    if not addresses:
        return 0
    task = contestant.navigation_task
    contest = task.contest
    track = getattr(contestant, "contestanttrack", None)
    aeroplane = contestant.team.aeroplane
    context = {
        "contestant": _crew_name(contestant),
        "aircraft": aeroplane.registration if aeroplane else "",
        "task": task.name,
        "contest": contest.name,
        "start_time": _format_time(contestant, contestant.starting_point_time),
        "finish_time": _format_time(contestant, contestant.finished_by_time),
        "crossed_finish": bool(track and track.passed_finish_gate),
        "score": f"{track.score:.0f}" if track else "",
        "state": track.current_state if track else "",
    }
    if kind == STARTED:
        template, url = CONTESTANT_STARTED_EMAIL, APP_URL + task.tracking_link
        subject = f"{context['contestant']} has started {task.name}"
    else:
        template = CONTESTANT_FINISHED_EMAIL
        url = APP_URL + fe_url("NAVIGATION_TASK_DETAIL", contestId=contest.pk, navigationTaskId=task.pk)
        subject = f"{context['contestant']} has finished {task.name}: {context['score']}"
    # Names come from users; Template autoescapes them in the HTML body
    html = Template(HEADER + template + EMAIL_SIGNATURE + FOOTER).render(Context({**context, "url": url}))
    converter = html2text.HTML2Text()
    converter.ignore_images = True
    text = converter.handle(html)
    # One e-mail per manager, so nobody sees the others' addresses
    for address in addresses:
        send_mail(subject, text, None, recipient_list=[address], html_message=html)
    return len(addresses)
