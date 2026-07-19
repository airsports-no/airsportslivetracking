from live_tracking_map import settings
from display.models import (
    AccessGrant,
    AccessResolution,
    ClubManagerMembership,
    Contest,
    ContestTokenAssignment,
)



def resolve_contest_access(contest: Contest) -> AccessResolution:
    contestants_used = contest.contestteam_set.count()
    tasks_used = contest.navigationtask_set.count()

    token_assignment = _contest_token_assignment(contest)
    if token_assignment is not None:
        return AccessResolution(
            tier_code=AccessGrant.TOKEN,
            tier_label=token_assignment.token_type.name,
            source_type="contest_token",
            source_id=token_assignment.id,
            contestant_limit=token_assignment.token_type.contestant_limit,
            task_limit=token_assignment.token_type.task_limit,
            contestants_used=contestants_used,
            tasks_used=tasks_used,
            enforcement_mode=settings.ACCESS_ENFORCEMENT_MODE,
            token_grant_id=token_assignment.token_grant_id,
            token_type_id=token_assignment.token_type_id,
        )

    contest_grant = _first_active_contest_grant(contest)
    if contest_grant is not None:
        return _resolution_from_grant(
            contest_grant,
            source_type="contest_override",
            contestants_used=contestants_used,
            tasks_used=tasks_used,
        )

    club_grant = _first_active_club_grant(contest)
    if club_grant is not None:
        return _resolution_from_grant(
            club_grant,
            source_type="club_pass",
            contestants_used=contestants_used,
            tasks_used=tasks_used,
        )

    return AccessResolution(
        tier_code=AccessGrant.FREE,
        tier_label="Free Training Tier",
        source_type="free_defaults",
        source_id=None,
        contestant_limit=settings.DEFAULT_FREE_CONTESTANT_LIMIT,
        task_limit=settings.DEFAULT_FREE_TASK_LIMIT,
        contestants_used=contestants_used,
        tasks_used=tasks_used,
        enforcement_mode=settings.ACCESS_ENFORCEMENT_MODE,
    )



def _contest_token_assignment(contest: Contest):
    try:
        return ContestTokenAssignment.objects.filter(contest=contest).select_related("token_grant", "token_type").first()
    except Exception:
        return None



def _first_active_contest_grant(contest: Contest):
    for grant in AccessGrant.objects.filter(contest=contest).order_by("-created_at"):
        if grant.is_active:
            return grant
    return None



def _first_active_club_grant(contest: Contest):
    if contest.organizing_club is None or contest.created_by is None:
        return None
    if not ClubManagerMembership.objects.filter(
        club=contest.organizing_club,
        user=contest.created_by,
        is_active=True,
    ).exists():
        return None
    for grant in AccessGrant.objects.filter(club=contest.organizing_club).order_by("-created_at"):
        if grant.is_active:
            return grant
    return None



def _resolution_from_grant(grant: AccessGrant, *, source_type: str, contestants_used: int, tasks_used: int) -> AccessResolution:
    return AccessResolution(
        tier_code=grant.tier,
        tier_label=grant.get_tier_display(),
        source_type=source_type,
        source_id=grant.id,
        contestant_limit=grant.contestant_limit,
        task_limit=grant.task_limit,
        contestants_used=contestants_used,
        tasks_used=tasks_used,
        enforcement_mode=settings.ACCESS_ENFORCEMENT_MODE,
    )
