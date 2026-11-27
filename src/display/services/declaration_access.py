"""
Who may read and change a contestant's declaration, until when, and what state it is in (D6, S21 of
documentation/PLAN_task_scoring_reliability.md). One place for the website's own-flights views, the apps' flight data
and the declaration endpoint of the pilot, so that they cannot disagree.
"""

import datetime
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist

from display.models import Contestant
from display.services.contestant_task_compiler import RELATIVE_TIMES, TIME_REFERENCE
from display.utilities.task_types import DECLARATION_NOT_NEEDED, DECLARATION_OPTIONAL, stored_task_type

ROLE_ORGANISER = "organiser"
ROLE_PILOT = "pilot"

STATE_MISSING = "missing"
STATE_INCOMPLETE = "incomplete"
STATE_COMPLETE = "complete"

# Payload keys that say how the declaration was made, not what was declared.
_META_KEYS = (TIME_REFERENCE, RELATIVE_TIMES)


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def is_crew_member(user, contestant: Contestant) -> bool:
    """
    Whether [user] is the pilot or the co-pilot of the flight. The same rule as the photo observations of the app
    (ContestantViewSet._is_crew_member): the e-mail address of the account is the one of a member of the crew.
    """
    email = (getattr(user, "email", "") or "").lower()
    crew = contestant.team.crew
    return bool(email) and any(
        member is not None and (member.email or "").lower() == email for member in (crew.member1, crew.member2)
    )


def declaration_role(user, contestant: Contestant, cache: Optional[dict] = None) -> Optional[str]:
    """ROLE_ORGANISER (may change the contest), ROLE_PILOT (crew of the flight) or None. [cache] saves the organiser check per contest."""
    if user is None or not user.is_authenticated:
        return None
    contest = contestant.navigation_task.contest
    if cache is None:
        cache = {}
    if contest.pk not in cache:
        cache[contest.pk] = user.has_perm("display.change_contest", contest)
    if cache[contest.pk]:
        return ROLE_ORGANISER
    return ROLE_PILOT if is_crew_member(user, contestant) else None


def declaration_cutoff(contestant: Contestant) -> datetime.datetime:
    """
    The last moment a pilot may change the declaration: the take-off time (D6). With an adaptive start the take-off time
    says nothing about when the flight begins (the start is whenever the starting line is crossed, from the tracker start
    on), so the cut-off is the earlier of the take-off time and the tracker start: the latest moment that is certainly
    before the flight can begin.
    """
    takeoff = contestant.takeoff_time or contestant.tracker_start_time
    if contestant.adaptive_start and contestant.tracker_start_time:
        return min(takeoff, contestant.tracker_start_time)
    return takeoff


def calculator_has_started(contestant: Contestant) -> bool:
    """The calculator reads the declaration when it starts, so a later change would not reach the scoring."""
    track = getattr(contestant, "contestanttrack", None)
    return bool(track and track.calculator_started)


def pilot_edit_refusal(contestant: Contestant, now: Optional[datetime.datetime] = None) -> Optional[str]:
    """Why a pilot may not change the declaration now, in words for the pilot; None when they may."""
    now = now or utcnow()
    if stored_task_type(contestant.navigation_task).declaration_need == DECLARATION_NOT_NEEDED:
        return "This task has no declaration."
    cutoff = declaration_cutoff(contestant)
    if now >= cutoff or calculator_has_started(contestant):
        local = cutoff.astimezone(contestant.navigation_task.contest.time_zone)
        return (
            f"The declaration can no longer be changed: it had to be done before take-off, at "
            f"{local:%H:%M} ({local:%Z}) on {local:%d %B %Y}. Ask the contest organiser if it has to be changed."
        )
    return None


def declaration_edit_path(contestant: Contestant) -> str:
    """The page (website path) where the declaration is edited. Change here when the pilot gets a page of their own (S22)."""
    task = contestant.navigation_task
    return f"/contestant-declaration/{task.contest_id}/{task.pk}/{contestant.pk}"


def _has_declared_something(payload: dict) -> bool:
    return any(value for key, value in (payload or {}).items() if key not in _META_KEYS)


def _route_errors(contestant: Contestant) -> list[str]:
    """The task's own validation errors (organiser matters), which the compiled configuration lists with the declaration's."""
    try:
        return list(contestant.navigation_task.compilednavigationtask.compiled_payload.get("validation_errors") or [])
    except ObjectDoesNotExist:
        return []


def declaration_status(
    contestant: Contestant,
    user=None,
    now: Optional[datetime.datetime] = None,
    role_cache: Optional[dict] = None,
) -> dict:
    """
    What the declaration of [contestant] needs and where it stands:
    need: "not_needed", "optional" or "required" (from the task type's registry entry).
    state: "missing" (nothing declared), "incomplete" (declared, but it does not hold yet) or "complete". A task without
        a declaration is "complete".
    errors: what is wrong, in plain language. A pilot only gets those of the declaration itself.
    can_edit: whether [user] may change it now, edit_until: the cut-off (ISO timestamp), edit_url: the page to do it on.
    The last three are only filled in for the flight's own crew and for organisers.
    """
    need = stored_task_type(contestant.navigation_task).declaration_need
    if need == DECLARATION_NOT_NEEDED:
        # Nothing to look up: also the answer for most flights, in lists
        return {
            "need": need,
            "state": STATE_COMPLETE,
            "errors": [],
            "can_edit": False,
            "edit_until": None,
            "edit_url": None,
        }
    role = declaration_role(user, contestant, role_cache)
    cutoff = declaration_cutoff(contestant)
    now = now or utcnow()

    config = getattr(contestant, "contestanttaskconfiguration", None)
    errors = list(config.validation_errors or []) if config else []
    if role == ROLE_PILOT:
        route_errors = set(_route_errors(contestant))
        errors = [error for error in errors if error not in route_errors]

    if not (config and _has_declared_something(config.declaration_payload)):
        # An optional declaration that was not made is not a problem, so it gets no error to fix
        state = STATE_MISSING
        if need == DECLARATION_OPTIONAL:
            errors = []
    elif errors:
        state = STATE_INCOMPLETE
    else:
        state = STATE_COMPLETE

    can_edit = role == ROLE_ORGANISER or (role == ROLE_PILOT and pilot_edit_refusal(contestant, now) is None)
    return {
        "need": need,
        "state": state,
        "errors": errors,
        "can_edit": can_edit,
        # An organiser may always change it, so there is no time to give them
        "edit_until": cutoff.isoformat() if role == ROLE_PILOT else None,
        "edit_url": declaration_edit_path(contestant) if role else None,
    }
