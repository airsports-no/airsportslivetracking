"""Announcements from the organizers to the pilots: who receives them, the push notification and the list for the app."""

import datetime

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from display.models import Contest, ContestAnnouncement, ContestTeam, Contestant, NavigationTask, Person
from display.services.push_notifications import send_to_person

# How long an announcement stays in the app after it was sent.
ANNOUNCEMENT_LIFETIME = datetime.timedelta(hours=24)


def recipients(contest: Contest, navigation_task: NavigationTask | None = None) -> list[Person]:
    """
    The crew members the announcement is for: those of the one task's contestants, or everybody registered in the contest
    (team signups and the contestants of its tasks).
    """
    if navigation_task is not None:
        crews = Contestant.objects.filter(navigation_task=navigation_task).values_list(
            "team__crew__member1", "team__crew__member2"
        )
    else:
        teams = ContestTeam.objects.filter(contest=contest).values_list("team__crew__member1", "team__crew__member2")
        contestants = Contestant.objects.filter(navigation_task__contest=contest).values_list(
            "team__crew__member1", "team__crew__member2"
        )
        crews = list(teams) + list(contestants)
    ids = {person_id for pair in crews for person_id in pair if person_id}
    return list(Person.objects.filter(pk__in=ids))


def send_announcement(announcement: ContestAnnouncement) -> int:
    """Pushes the announcement to the phones of the recipients; returns how many people were reached."""
    reached = 0
    for person in recipients(announcement.contest, announcement.navigation_task):
        if (
            send_to_person(
                person,
                announcement.contest.name,
                announcement.message,
                {"type": "announcement", "contest_id": str(announcement.contest_id)},
            )
            > 0
        ):
            reached += 1
    announcement.people_reached = reached
    announcement.save(update_fields=["people_reached"])
    return reached


def announcements_for(person: Person, now: datetime.datetime = None) -> list[ContestAnnouncement]:
    """The announcements still showing that concern this person (newest first)."""
    now = now or timezone.now()
    in_crew = Q(team__crew__member1=person) | Q(team__crew__member2=person)
    contest_ids = set(ContestTeam.objects.filter(in_crew).values_list("contest_id", flat=True))
    task_ids = set(Contestant.objects.filter(in_crew).values_list("navigation_task_id", flat=True))
    contest_ids |= set(Contestant.objects.filter(in_crew).values_list("navigation_task__contest_id", flat=True))
    return list(
        ContestAnnouncement.objects.filter(
            Q(contest_id__in=contest_ids) & (Q(navigation_task__isnull=True) | Q(navigation_task_id__in=task_ids)),
            created_at__gte=now - ANNOUNCEMENT_LIFETIME,
        )
        .select_related("contest", "navigation_task")
        .order_by("-created_at")
    )
