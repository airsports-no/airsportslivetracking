import datetime

from django.conf import settings
from display.models import (
    AccessGrant,
    AccessResolution,
    Contest,
    ContestTokenAssignment,
    ContestUsageLedger,
    Contestant,
)


def resolve_contest_access(contest: Contest) -> AccessResolution:
    contestants_used = ContestUsageLedger.objects.filter(
        contest=contest,
        kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
    ).count()
    if contestants_used == 0:
        contestants_used = _backfill_missing_historical_usage(contest)

    token_assignment = _contest_token_assignment(contest)
    if token_assignment is not None:
        return _apply_more_advantageous_free_defaults(
            AccessResolution(
                tier_code=AccessGrant.TOKEN,
                tier_label=token_assignment.token_type.name,
                source_type="contest_token",
                source_id=token_assignment.id,
                contestant_limit=token_assignment.token_type.contestant_limit,
                contestants_used=contestants_used,
                enforcement_mode=settings.ACCESS_ENFORCEMENT_MODE,
                token_grant_id=token_assignment.token_grant_id,
                token_type_id=token_assignment.token_type_id,
            )
        )

    contest_grant = _first_active_contest_grant(contest)
    if contest_grant is not None:
        return _apply_more_advantageous_free_defaults(
            _resolution_from_grant(
                contest_grant,
                source_type="contest_override",
                contestants_used=contestants_used,
            )
        )

    club_grant = _first_active_club_grant(contest)
    if club_grant is not None:
        return _apply_more_advantageous_free_defaults(
            _resolution_from_grant(
                club_grant,
                source_type="club_pass",
                contestants_used=contestants_used,
            )
        )

    return AccessResolution(
        tier_code=AccessGrant.FREE,
        tier_label="Free Training Tier",
        source_type="free_defaults",
        source_id=None,
        contestant_limit=settings.DEFAULT_FREE_CONTESTANT_LIMIT,
        contestants_used=contestants_used,
        enforcement_mode=settings.ACCESS_ENFORCEMENT_MODE,
        free_contestant_limit=settings.DEFAULT_FREE_CONTESTANT_LIMIT,
    )


def _backfill_missing_historical_usage(contest: Contest) -> int:
    started_contestants = Contestant.objects.filter(
        navigation_task__contest=contest,
        contestanttrack__calculator_started=True,
    ).select_related("navigation_task", "team__crew").distinct()
    owner_person_id = None
    if contest.created_by_id:
        try:
            owner_person_id = contest.created_by.person.id
        except Exception:
            owner_person_id = None
    for contestant in started_contestants:
        if owner_person_id is not None and contestant.team.crew.member1_id == owner_person_id:
            continue
        pilot = contestant.team.crew.member1
        ContestUsageLedger.objects.get_or_create(
            contest=contest,
            pilot=pilot,
            kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
            defaults={
                "navigation_task": contestant.navigation_task,
                "team": contestant.team,
                "contestant": contestant,
            },
        )
        ContestUsageLedger.objects.get_or_create(
            contest=contest,
            navigation_task=contestant.navigation_task,
            pilot=pilot,
            kind=ContestUsageLedger.TASK_PILOT_STARTED,
            defaults={
                "team": contestant.team,
                "contestant": contestant,
            },
        )
    return ContestUsageLedger.objects.filter(
        contest=contest,
        kind=ContestUsageLedger.CONTEST_PILOT_STARTED,
    ).count()


def _contest_token_assignment(contest: Contest):
    try:
        assignment = ContestTokenAssignment.objects.filter(contest=contest).select_related("token_grant", "token_type").first()
        if assignment is None:
            return None
        if assignment.expires_at is not None and assignment.expires_at <= datetime.datetime.now(datetime.timezone.utc):
            return None
        return assignment
    except Exception:
        return None


def _first_active_contest_grant(contest: Contest):
    for grant in AccessGrant.objects.filter(contest=contest).order_by("-created_at"):
        if grant.is_active:
            return grant
    return None


def _first_active_club_grant(contest: Contest):
    if contest.organizing_club is None:
        return None
    for grant in AccessGrant.objects.filter(club=contest.organizing_club).order_by("-created_at"):
        if grant.is_active:
            return grant
    return None


def _resolution_from_grant(grant: AccessGrant, *, source_type: str, contestants_used: int) -> AccessResolution:
    return AccessResolution(
        tier_code=grant.tier,
        tier_label=grant.get_tier_display(),
        source_type=source_type,
        source_id=grant.id,
        contestant_limit=grant.contestant_limit,
        contestants_used=contestants_used,
        enforcement_mode=settings.ACCESS_ENFORCEMENT_MODE,
    )


def _apply_more_advantageous_free_defaults(resolution: AccessResolution) -> AccessResolution:
    effective_contestant_limit, contestant_uses_free = _most_advantageous_limit(
        resolution.contestant_limit,
        settings.DEFAULT_FREE_CONTESTANT_LIMIT,
    )
    resolution.package_contestant_limit = resolution.contestant_limit
    resolution.free_contestant_limit = settings.DEFAULT_FREE_CONTESTANT_LIMIT
    resolution.contestant_limit = effective_contestant_limit
    resolution.contestant_limit_uses_free_default = contestant_uses_free
    return resolution


def _most_advantageous_limit(package_limit: int | None, free_limit: int | None) -> tuple[int | None, bool]:
    if package_limit is None:
        return None, False
    if free_limit is None:
        return None, True
    if free_limit > package_limit:
        return free_limit, True
    return package_limit, False
