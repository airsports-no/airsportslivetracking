"""
Admin team registration/edit, replacing RegisterTeamWizard.done(). Used by
AdminTeamRegistrationSerialiser (the React admin registration flow's backend) - see the
wizard->SPA migration plan's slice 4.

Mirrors SignupSerialiser.create()'s locking/capacity/duplicate-registration pattern rather than
RegisterTeamWizard's, which had none of it: no row locking (two concurrent admin registrations for
the last slot could both succeed), no assert_can_register_team call at all (admins could register
past the contest's resolved capacity while public signup was correctly blocked), and no
duplicate/cross-team/self-as-copilot checks.
"""

from django.core.exceptions import ValidationError as CoreValidationError
from django.db import transaction
from django.db.models import Q

from display.models import Aeroplane, Club, Contest, ContestTeam, Crew, Team
from display.services.capacity_enforcement import assert_can_register_team


def _assert_no_conflicting_registration(contest, team, *, pilot, copilot, exclude_contest_team=None):
    existing = ContestTeam.objects.filter(
        Q(team__crew__member1=pilot) | Q(team__crew__member2=pilot),
        contest=contest,
    ).exclude(team=team)
    if exclude_contest_team is not None:
        existing = existing.exclude(pk=exclude_contest_team.pk)
    if existing.exists():
        raise CoreValidationError(
            f"{pilot} is already registered for contest {contest} in a different team: "
            f"{[str(item) for item in existing]}"
        )
    if copilot is not None:
        existing = ContestTeam.objects.filter(
            Q(team__crew__member1=copilot) | Q(team__crew__member2=copilot),
            contest=contest,
        ).exclude(team=team)
        if exclude_contest_team is not None:
            existing = existing.exclude(pk=exclude_contest_team.pk)
        if existing.exists():
            raise CoreValidationError(
                f"{copilot} is already registered for contest {contest} in a different team: "
                f"{[str(item) for item in existing]}"
            )


def get_or_create_aeroplane(registration: str, defaults: dict | None = None) -> Aeroplane:
    """
    Reuse an existing aeroplane by registration untouched - only apply type/colour/etc. when
    actually creating a new row. RegisterTeamWizard's done() unconditionally overwrote an existing
    (possibly shared, possibly another team's) aeroplane's colour/type/picture on every
    registration that reused it; this is the fix.
    """
    aeroplane, _ = Aeroplane.objects.get_or_create(registration=registration, defaults=defaults or {})
    return aeroplane


def get_or_create_club(name: str, defaults: dict | None = None) -> Club:
    """Same non-mutating-on-reuse fix as get_or_create_aeroplane, for Club.country/logo."""
    club, _ = Club.objects.get_or_create(name=name, defaults=defaults or {})
    return club


def commit_team_registration(
    contest: Contest,
    *,
    pilot,
    copilot=None,
    aeroplane: Aeroplane,
    club: Club,
    tracking_data: dict,
    original_team: Team | None = None,
) -> ContestTeam:
    """
    Lock the contest, materialize the Crew/Team, enforce capacity and duplicate-registration
    rules, then call Contest.replace_team - all inside one transaction, so a rejection here rolls
    back the Crew/Team rows too rather than leaving them behind (RegisterTeamWizard.done() was not
    atomic at all).

    `original_team`, when given, is the team being replaced (an edit of an existing
    registration) - matches Contest.replace_team's contract, and is excluded from the
    duplicate-registration check against itself.
    """
    if copilot is not None and copilot == pilot:
        raise CoreValidationError("The pilot and co-pilot cannot be the same person")

    with transaction.atomic():
        Contest.objects.select_for_update().get(pk=contest.pk)
        crew, _ = Crew.objects.get_or_create(member1=pilot, member2=copilot)
        team, _ = Team.objects.get_or_create(crew=crew, aeroplane=aeroplane, club=club)

        # assert_can_register_team's capacity check is a coarse freeze: once the contest's
        # guest-pilot usage (ContestUsageLedger, not registration count) is at its limit, no new
        # non-owner pilot may be registered. An edit that keeps the same pilot doesn't register
        # anyone new, so it must not be rejected just because the contest happens to be at that
        # freeze for reasons unrelated to this edit - but an edit that *replaces* the pilot with
        # someone not previously on this registration is, capacity-wise, indistinguishable from a
        # fresh registration for that pilot, and must still be checked (CodeRabbit review finding
        # on PR #785: the unconditional skip let an edit swap in a brand-new pilot at a contest
        # that's otherwise frozen for new registrations).
        same_pilot_edit = original_team is not None and original_team.crew.member1_id == pilot.id
        if not same_pilot_edit:
            assert_can_register_team(contest, team)
        exclude_contest_team = None
        if original_team is not None:
            exclude_contest_team = ContestTeam.objects.filter(contest=contest, team=original_team).first()
        if (
            ContestTeam.objects.filter(contest=contest, team=team)
            .exclude(pk=exclude_contest_team.pk if exclude_contest_team else None)
            .exists()
        ):
            raise CoreValidationError(f"Team {team} is already registered for contest {contest}")
        _assert_no_conflicting_registration(
            contest, team, pilot=pilot, copilot=copilot, exclude_contest_team=exclude_contest_team
        )

        return contest.replace_team(original_team, team, tracking_data)
