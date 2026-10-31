"""
Every flight one person has flown, as pilot or co-pilot, for the site admins' user flights page: whatever the visibility
of the contest, with the result and which AI summaries have been written of it.
"""

from django.db.models import Q

from display.models import Contestant, FlightSummary, MyUser, Person

PILOT = "pilot"
CO_PILOT = "co-pilot"


def _role(contestant: Contestant, person: Person) -> str:
    return PILOT if contestant.team.crew.member1_id == person.pk else CO_PILOT


def _partner(contestant: Contestant, person: Person) -> str | None:
    crew = contestant.team.crew
    partner = crew.member2 if crew.member1_id == person.pk else crew.member1
    return str(partner) if partner else None


def _summary_styles(contestants: list[Contestant]) -> dict[int, list[str]]:
    """The styles of the AI summaries written for each flight's current scores."""
    versions = {contestant.pk: (contestant.track_version, contestant.score_version) for contestant in contestants}
    styles: dict[int, set[str]] = {}
    for contestant_id, track_version, score_version, style in FlightSummary.objects.filter(
        contestant_id__in=versions, status=FlightSummary.STATUS_DONE
    ).values_list("contestant_id", "track_version", "score_version", "style"):
        if versions[contestant_id] == (track_version, score_version):
            styles.setdefault(contestant_id, set()).add(style)
    return {contestant_id: sorted(found) for contestant_id, found in styles.items()}


def _flight(contestant: Contestant, person: Person, summary_styles: list[str]) -> dict:
    navigation_task = contestant.navigation_task
    track = getattr(contestant, "contestanttrack", None)
    return {
        "id": contestant.pk,
        "contestant_number": contestant.contestant_number,
        "contest_id": navigation_task.contest_id,
        "contest_name": navigation_task.contest.name,
        "navigation_task_id": navigation_task.pk,
        "navigation_task_name": navigation_task.name,
        "task_type": navigation_task.scorecard.get_calculator_display() if navigation_task.scorecard else None,
        "role": _role(contestant, person),
        "partner": _partner(contestant, person),
        "aeroplane": contestant.team.aeroplane.registration,
        "flight_mode": contestant.flight_mode,
        "takeoff_time": contestant.takeoff_time,
        "finished_by_time": contestant.finished_by_time,
        "calculator_started": bool(track and track.calculator_started),
        "calculator_finished": bool(track and track.calculator_finished),
        # Before scoring starts the track holds the scorecard's initial score, which is not a result
        "score": track.score if track and track.calculator_started else None,
        "summary_styles": summary_styles,
    }


def user_flights(person: Person) -> dict:
    contestants = list(
        Contestant.objects.filter(Q(team__crew__member1=person) | Q(team__crew__member2=person))
        .select_related(
            "navigation_task__contest",
            "navigation_task__scorecard",
            "team__crew__member1",
            "team__crew__member2",
            "team__aeroplane",
            "contestanttrack",
        )
        .order_by("-takeoff_time")
        .distinct()
    )
    summary_styles = _summary_styles(contestants)
    return {
        "person": {
            "id": person.pk,
            "name": str(person),
            "email": person.email,
            "has_account": MyUser.objects.filter(email__iexact=person.email).exists(),
        },
        "flights": [_flight(contestant, person, summary_styles.get(contestant.pk, [])) for contestant in contestants],
    }
