from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from display.models import ContestUsageLedger, Contestant, ContestTeam
from display.services.access_resolver import resolve_contest_access
from display.services.task_type_visibility import get_user_granted_task_type_groups
from display.services.token_assignment import ensure_token_assignment_active_for_guest_start
from display.utilities.task_type_group_definitions import get_task_type_group


def _get_owner_person_id(contest):
    if not contest.created_by_id:
        return None
    try:
        return contest.created_by.person.id
    except ObjectDoesNotExist:
        return None


def _should_enforce(resolution) -> bool:
    return resolution.enforcement_mode == "enforce"


def _normalized_enforcement_mode() -> str:
    configured = getattr(settings, "ACCESS_ENFORCEMENT_MODE", "audit")
    return configured if configured in {"audit", "enforce"} else "audit"


def _is_owner_team(contest, team) -> bool:
    if not contest.created_by_id or team is None:
        return False
    owner_person = contest.created_by.person
    return team.crew.member1_id == owner_person.id


def _guest_pilot_has_contest_slot(contest, pilot) -> bool:
    return ContestUsageLedger.objects.filter(
        contest=contest,
        pilot=pilot,
        kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
    ).exists()


def _guest_pilot_has_task_slot(contest, navigation_task, pilot) -> bool:
    return ContestUsageLedger.objects.filter(
        contest=contest,
        navigation_task=navigation_task,
        pilot=pilot,
        kind=ContestUsageLedger.TASK_PILOT_STARTED,
    ).exists()


def scheduling_capacity_preview(navigation_task, selected_contest_team_ids, first_takeoff_time=None):
    contest = navigation_task.contest
    resolution = resolve_contest_access(contest)
    limit = resolution.contestant_limit
    owner_person_id = _get_owner_person_id(contest)

    existing_contestants = navigation_task.contestant_set.all()
    if first_takeoff_time is not None:
        existing_contestants = existing_contestants.filter(
            finished_by_time__gte=first_takeoff_time,
        )

    started_pilot_ids = set(
        ContestUsageLedger.objects.filter(
            contest=contest,
            navigation_task=navigation_task,
            kind=ContestUsageLedger.TASK_PILOT_STARTED,
        ).values_list("pilot_id", flat=True)
    )
    started_pilot_ids.discard(None)

    existing_registered_pilot_ids = set(existing_contestants.values_list("team__crew__member1_id", flat=True))
    existing_registered_pilot_ids.discard(None)

    selected_team_ids = {int(team_id) for team_id in selected_contest_team_ids}
    selected_contest_teams = ContestTeam.objects.filter(
        contest=contest,
        pk__in=selected_team_ids,
    ).select_related("team__crew")
    if selected_contest_teams.count() != len(selected_team_ids):
        raise ValidationError("One or more selected contest teams do not belong to this contest.")
    selected_pilot_ids = {
        ct.team.crew.member1_id
        for ct in selected_contest_teams
        if ct.team_id and ct.team.crew_id and ct.team.crew.member1_id is not None
    }

    if owner_person_id is not None:
        started_pilot_ids.discard(owner_person_id)
        existing_registered_pilot_ids.discard(owner_person_id)
        selected_pilot_ids.discard(owner_person_id)

    reserved_before = started_pilot_ids | existing_registered_pilot_ids
    reserved_after = started_pilot_ids | existing_registered_pilot_ids | selected_pilot_ids
    additional_selected_pilot_ids = selected_pilot_ids - reserved_before

    return {
        "contestant_limit": limit,
        "reserved_before_count": len(reserved_before),
        "reserved_after_count": len(reserved_after),
        "additional_selected_count": len(additional_selected_pilot_ids),
        "remaining_before_count": None if limit is None else max(limit - len(reserved_before), 0),
        "remaining_after_count": None if limit is None else max(limit - len(reserved_after), 0),
        "would_exceed": False if limit is None else len(reserved_after) > limit,
    }


def _contestant_limit_error_message(resolution):
    limit = resolution.contestant_limit
    used = resolution.contestants_used
    if limit is None:
        return "This contest cannot accept more pilots right now."
    remaining = max(limit - used, 0)
    return (
        f"This contestant would exceed the active pilot capacity for the contest. "
        f"Capacity: {used} / {limit} competing pilots already reserved or historically used. "
        f"Remaining available pilot slots: {remaining}. "
        f"To proceed, reuse an already-counted pilot, remove an unstarted contestant, or apply a larger token or club pass."
    )


def _task_type_group_error_message(task_type_group):
    task_group_label = task_type_group.replace("_", " ")
    return (
        f"This task requires the {task_group_label} task package, but the current contest only has access to other task groups. "
        f"To create this task, apply a token or annual club pass that includes {task_group_label} access, or ask an organizer with access to update the contest package."
    )


def _task_reserved_guest_pilots(contest, navigation_task, current_contestant=None):
    owner_person_id = _get_owner_person_id(contest)

    started_pilot_ids = set(
        ContestUsageLedger.objects.filter(
            contest=contest,
            navigation_task=navigation_task,
            kind=ContestUsageLedger.TASK_PILOT_STARTED,
        ).values_list("pilot_id", flat=True)
    )
    started_pilot_ids.discard(None)

    registered_contestants = Contestant.objects.filter(
        navigation_task=navigation_task,
    )
    if current_contestant is not None and current_contestant.pk is not None:
        registered_contestants = registered_contestants.exclude(pk=current_contestant.pk)
    registered_pilot_ids = set(registered_contestants.values_list("team__crew__member1_id", flat=True))
    registered_pilot_ids.discard(None)
    if owner_person_id is not None:
        registered_pilot_ids.discard(owner_person_id)
        started_pilot_ids.discard(owner_person_id)

    return started_pilot_ids | registered_pilot_ids


def _contest_reserved_guest_pilots(contest, current_contestant=None):
    owner_person_id = _get_owner_person_id(contest)

    started_pilot_ids = set(
        ContestUsageLedger.objects.filter(
            contest=contest,
            kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
        ).values_list("pilot_id", flat=True)
    )
    started_pilot_ids.discard(None)

    registered_contestants = Contestant.objects.filter(
        navigation_task__contest=contest,
    )
    if current_contestant is not None and current_contestant.pk is not None:
        registered_contestants = registered_contestants.exclude(pk=current_contestant.pk)
    registered_pilot_ids = set(registered_contestants.values_list("team__crew__member1_id", flat=True))
    registered_pilot_ids.discard(None)

    if owner_person_id is not None:
        started_pilot_ids.discard(owner_person_id)
        registered_pilot_ids.discard(owner_person_id)

    return started_pilot_ids | registered_pilot_ids


def _assert_can_reserve_task_slot(navigation_task, team, resolution, current_contestant=None):
    contest = navigation_task.contest
    if _is_owner_team(contest, team):
        return resolution
    if not _should_enforce(resolution) or resolution.contestant_limit is None:
        return resolution

    pilot = team.crew.member1
    if _guest_pilot_has_task_slot(contest, navigation_task, pilot):
        return resolution

    reserved_pilot_ids = _task_reserved_guest_pilots(contest, navigation_task, current_contestant=current_contestant)
    if pilot.id in reserved_pilot_ids:
        return resolution

    contest_reserved_pilot_ids = _contest_reserved_guest_pilots(contest, current_contestant=current_contestant)
    if pilot.id in contest_reserved_pilot_ids:
        return resolution

    if len(reserved_pilot_ids) >= resolution.contestant_limit:
        raise ValidationError(_contestant_limit_error_message(resolution))
    if len(contest_reserved_pilot_ids) >= resolution.contestant_limit:
        raise ValidationError(_contestant_limit_error_message(resolution))
    return resolution


def assert_can_add_navigation_task(contest, task_type=None, task_subtype=None, user=None):
    resolution = resolve_contest_access(contest)
    normalized_mode = _normalized_enforcement_mode()
    if getattr(resolution, "enforcement_mode", normalized_mode) != normalized_mode:
        resolution.enforcement_mode = normalized_mode
    token_assignment = getattr(contest, "contesttokenassignment", None)
    if token_assignment is not None and token_assignment.expires_at is not None and token_assignment.expires_at <= timezone.now():
        raise ValidationError("This contest token has expired. The contest is now in archive mode until a new token or annual pass is applied.")
    task_type_group = get_task_type_group(task_type=task_type, task_subtype=task_subtype)
    allowed_task_type_groups = set(getattr(resolution, "allowed_task_type_groups", ["legacy"]))
    # A user who has been explicitly granted a task-type group (e.g. a beta
    # tester managing a club with a "cima" access grant, or a token holder)
    # may use that group in any contest they organize, independent of that
    # contest's own resolved access. This decouples "who may use the
    # feature" (user/beta) from "who pays for pilots" (contest/club). Note
    # this deliberately does NOT use get_visible_task_type_groups_for_user,
    # which falls back to "everything" whenever the global visibility gate
    # is off - that's a UI-dropdown default, not an entitlement, and must
    # not bypass enforcement here.
    if user is not None:
        allowed_task_type_groups.update(get_user_granted_task_type_groups(user))
        resolution.allowed_task_type_groups = sorted(allowed_task_type_groups)
    if task_type_group not in allowed_task_type_groups:
        raise ValidationError(_task_type_group_error_message(task_type_group))
    return resolution


def assert_can_register_team(contest, team=None):
    resolution = resolve_contest_access(contest)
    if _is_owner_team(contest, team):
        return resolution
    if _should_enforce(resolution) and resolution.contestant_limit is not None and resolution.contestants_used >= resolution.contestant_limit:
        raise ValidationError(_contestant_limit_error_message(resolution))
    return resolution


def assert_can_self_register_contestant(navigation_task, contest_team):
    resolution = resolve_contest_access(navigation_task.contest)
    return _assert_can_reserve_task_slot(navigation_task, contest_team.team, resolution)


def assert_can_start_contestant(contestant):
    contest = contestant.navigation_task.contest
    team = contestant.team
    pilot = team.crew.member1
    navigation_task = contestant.navigation_task
    resolution = resolve_contest_access(contest)
    _assert_can_reserve_task_slot(navigation_task, team, resolution)
    if _is_owner_team(contest, team):
        return resolution
    ensure_token_assignment_active_for_guest_start(contest)
    if _guest_pilot_has_task_slot(contest, navigation_task, pilot):
        return resolution
    task_started_pilots = ContestUsageLedger.objects.filter(
        contest=contest,
        navigation_task=navigation_task,
        kind=ContestUsageLedger.TASK_PILOT_STARTED,
    ).count()
    if _should_enforce(resolution) and resolution.contestant_limit is not None:
        if task_started_pilots >= resolution.contestant_limit:
            raise ValidationError(_contestant_limit_error_message(resolution))
        if resolution.contestants_used >= resolution.contestant_limit and not _guest_pilot_has_contest_slot(contest, pilot):
            raise ValidationError(_contestant_limit_error_message(resolution))
    return resolution
