import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.test import TestCase
from django.utils import timezone

from display.models import (
    Contest,
    ContestTokenAssignment,
    TokenType,
    UserTokenGrant,
    ContestUsageLedger,
    NavigationTask,
    Route,
    Scorecard,
    Contestant,
    ContestantTrack,
    Team,
    Crew,
    Person,
    Aeroplane,
    Club,
    AccessGrant,
)
from display.services.access_resolver import resolve_contest_access
from display.services.capacity_enforcement import assert_can_add_navigation_task, assert_can_start_contestant
from display.services.token_assignment import assign_token_to_contest, revert_token_assignment_for_support


class TestTokenAssignment(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="token-owner@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.user.email)
        self.contest = Contest.objects.create(
            name="Token Contest",
            time_zone="Europe/Oslo",
            start_time=datetime.datetime(2026, 6, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 6, 1, 17, 0, tzinfo=datetime.timezone.utc),
            location="60.0,11.0",
            created_by=self.user,
        )
        self.token_type = TokenType.objects.create(
            name="Club event 25/3",
            contestant_limit=25,
            validity_days=14,
        )
        self.annual_token_type = TokenType.objects.create(
            name="Annual club pass 15",
            contestant_limit=15,
            validity_days=365,
        )

    def test_user_token_grant_reports_remaining_quantity(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=5,
            quantity_consumed=2,
        )

        self.assertEqual(3, grant.quantity_remaining)
        self.assertTrue(grant.has_available_tokens)

    def test_assign_token_to_contest_consumes_one_token_and_links_assignment(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=2,
            quantity_consumed=0,
        )

        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        grant.refresh_from_db()

        self.assertEqual(1, grant.quantity_consumed)
        self.assertEqual(1, grant.quantity_remaining)
        self.assertEqual(self.contest, assignment.contest)
        self.assertEqual(grant, assignment.token_grant)
        self.assertEqual(self.token_type, assignment.token_type)
        self.assertEqual(ContestTokenAssignment.objects.get(contest=self.contest), assignment)

    def test_assign_token_to_contest_backfills_started_usage_for_existing_contest(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=2,
            quantity_consumed=0,
        )
        scorecard = Scorecard.objects.create(name="Backfill card", shortcut_name="backfill-card")
        person = Person.objects.create(first_name="Pilot", last_name="One", email="pilot-backfill@example.com")
        team = Team.objects.create(
            crew=Crew.objects.create(member1=person),
            aeroplane=Aeroplane.objects.create(registration="LN-BACKFILL"),
        )
        task = NavigationTask.objects.create(
            name="Backfill Task",
            contest=self.contest,
            route=Route.objects.create(name="Backfill Route"),
            original_scorecard=scorecard,
            start_time=datetime.datetime(2026, 6, 1, 9, 0, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 6, 1, 17, 0, tzinfo=datetime.timezone.utc),
        )
        contestant = Contestant.objects.create(
            team=team,
            navigation_task=task,
            contestant_number=1,
            takeoff_time=datetime.datetime(2026, 6, 1, 10, 0, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 6, 1, 9, 50, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 6, 1, 12, 0, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        ContestantTrack.objects.get(contestant=contestant).set_calculator_started()

        assign_token_to_contest(self.contest, self.user, grant.id)

        resolution = resolve_contest_access(self.contest)
        self.assertEqual(1, resolution.contestants_used)
        self.assertTrue(
            ContestUsageLedger.objects.filter(
                contest=self.contest,
                navigation_task=task,
                kind=ContestUsageLedger.TASK_PILOT_STARTED,
                pilot=person,
            ).exists()
        )
        self.assertEqual(1, ContestUsageLedger.objects.filter(contest=self.contest, kind=ContestUsageLedger.CONTEST_PILOT_STARTED).count())
        self.assertEqual(1, ContestUsageLedger.objects.filter(contest=self.contest, kind=ContestUsageLedger.TASK_PILOT_STARTED).count())

    def test_support_revert_token_assignment_refunds_token_and_removes_assignment(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=2,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)

        reverted_grant = revert_token_assignment_for_support(assignment, self.user)
        reverted_grant.refresh_from_db()

        self.assertEqual(0, reverted_grant.quantity_consumed)
        self.assertFalse(ContestTokenAssignment.objects.filter(pk=assignment.pk).exists())

    def test_assign_token_to_contest_rejects_exhausted_grant(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=1,
        )

        with self.assertRaises(ValidationError):
            assign_token_to_contest(self.contest, self.user, grant.id)

    def test_assign_token_to_contest_rejects_other_users_grant(self):
        other_user = get_user_model().objects.create(email="other@example.com")
        grant = UserTokenGrant.objects.create(
            user=other_user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )

        with self.assertRaises(ValidationError):
            assign_token_to_contest(self.contest, self.user, grant.id)

    def test_assignment_starts_inactive_until_first_guest_start(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)

        self.assertIsNone(getattr(assignment, "activated_at", None))
        self.assertIsNone(getattr(assignment, "expires_at", None))

    def test_owner_only_start_does_not_activate_token(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        scorecard = Scorecard.objects.create(name="Owner card", shortcut_name="owner-card")
        task = NavigationTask.objects.create(
            name="Owner Task",
            contest=self.contest,
            route=Route.objects.create(name="Owner Route"),
            original_scorecard=scorecard,
            start_time=timezone.now(),
            finish_time=timezone.now() + timezone.timedelta(hours=2),
        )
        owner_team = Team.objects.create(
            crew=Crew.objects.create(member1=self.owner_person),
            aeroplane=Aeroplane.objects.create(registration="LN-OWNER-TTL"),
        )
        owner_contestant = Contestant.objects.create(
            team=owner_team,
            navigation_task=task,
            contestant_number=1,
            takeoff_time=timezone.now(),
            tracker_start_time=timezone.now() - timezone.timedelta(minutes=10),
            finished_by_time=timezone.now() + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

        ContestantTrack.objects.get(contestant=owner_contestant).set_calculator_started()
        assignment.refresh_from_db()

        self.assertIsNone(getattr(assignment, "activated_at", None))
        self.assertIsNone(getattr(assignment, "expires_at", None))

    def test_first_guest_start_activates_token_and_sets_expiry(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        scorecard = Scorecard.objects.create(name="Guest card", shortcut_name="guest-card")
        task = NavigationTask.objects.create(
            name="Guest Task",
            contest=self.contest,
            route=Route.objects.create(name="Guest Route"),
            original_scorecard=scorecard,
            start_time=timezone.now(),
            finish_time=timezone.now() + timezone.timedelta(hours=2),
        )
        pilot = Person.objects.create(first_name="Guest", last_name="Pilot", email="guest-ttl@example.com")
        guest_team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-GUEST-TTL"),
        )
        guest_contestant = Contestant.objects.create(
            team=guest_team,
            navigation_task=task,
            contestant_number=1,
            takeoff_time=timezone.now(),
            tracker_start_time=timezone.now() - timezone.timedelta(minutes=10),
            finished_by_time=timezone.now() + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

        ContestantTrack.objects.get(contestant=guest_contestant).set_calculator_started()
        assignment.refresh_from_db()

        self.assertIsNotNone(assignment.activated_at)
        self.assertIsNotNone(assignment.expires_at)
        self.assertEqual(14, (assignment.expires_at - assignment.activated_at).days)

    def test_first_guest_start_activates_annual_token_for_365_days(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.annual_token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        scorecard = Scorecard.objects.create(name="Annual guest card", shortcut_name="annual-guest-card")
        task = NavigationTask.objects.create(
            name="Annual Guest Task",
            contest=self.contest,
            route=Route.objects.create(name="Annual Guest Route"),
            original_scorecard=scorecard,
            start_time=timezone.now(),
            finish_time=timezone.now() + timezone.timedelta(hours=2),
        )
        pilot = Person.objects.create(first_name="Annual", last_name="Pilot", email="annual-guest@example.com")
        guest_team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-ANNUAL-TTL"),
        )
        guest_contestant = Contestant.objects.create(
            team=guest_team,
            navigation_task=task,
            contestant_number=1,
            takeoff_time=timezone.now(),
            tracker_start_time=timezone.now() - timezone.timedelta(minutes=10),
            finished_by_time=timezone.now() + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

        ContestantTrack.objects.get(contestant=guest_contestant).set_calculator_started()
        assignment.refresh_from_db()

        self.assertIsNotNone(assignment.activated_at)
        self.assertIsNotNone(assignment.expires_at)
        self.assertEqual(365, (assignment.expires_at - assignment.activated_at).days)

    def test_expired_token_blocks_new_guest_start(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        assignment.activated_at = timezone.now() - timezone.timedelta(days=15)
        assignment.expires_at = timezone.now() - timezone.timedelta(days=1)
        assignment.save(update_fields=["activated_at", "expires_at"])
        scorecard = Scorecard.objects.create(name="Expired card", shortcut_name="expired-card")
        task = NavigationTask.objects.create(
            name="Expired Task",
            contest=self.contest,
            route=Route.objects.create(name="Expired Route"),
            original_scorecard=scorecard,
            start_time=timezone.now(),
            finish_time=timezone.now() + timezone.timedelta(hours=2),
        )
        pilot = Person.objects.create(first_name="Expired", last_name="Pilot", email="expired-pilot@example.com")
        guest_team = Team.objects.create(
            crew=Crew.objects.create(member1=pilot),
            aeroplane=Aeroplane.objects.create(registration="LN-EXP-TTL"),
        )
        guest_contestant = Contestant.objects.create(
            team=guest_team,
            navigation_task=task,
            contestant_number=1,
            takeoff_time=timezone.now(),
            tracker_start_time=timezone.now() - timezone.timedelta(minutes=10),
            finished_by_time=timezone.now() + timezone.timedelta(hours=2),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )

        with self.assertRaises(ValidationError):
            assert_can_start_contestant(guest_contestant)

    def test_expired_token_blocks_new_task_creation(self):
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        assignment.activated_at = timezone.now() - timezone.timedelta(days=15)
        assignment.expires_at = timezone.now() - timezone.timedelta(days=1)
        assignment.save(update_fields=["activated_at", "expires_at"])

        with self.assertRaises(DRFValidationError):
            assert_can_add_navigation_task(self.contest)

    def test_expired_token_falls_through_to_active_club_pass_in_resolver(self):
        club = Club.objects.create(name="Archive Club")
        self.contest.organizing_club = club
        self.contest.save(update_fields=["organizing_club"])
        from display.models import ClubManagerMembership
        ClubManagerMembership.objects.create(club=club, user=self.user, role=ClubManagerMembership.OWNER, is_active=True)
        AccessGrant.objects.create(
            club=club,
            status=AccessGrant.ACTIVE,
            contestant_limit=12,
        )
        grant = UserTokenGrant.objects.create(
            user=self.user,
            token_type=self.token_type,
            quantity_total=1,
            quantity_consumed=0,
        )
        assignment = assign_token_to_contest(self.contest, self.user, grant.id)
        assignment.activated_at = timezone.now() - timezone.timedelta(days=15)
        assignment.expires_at = timezone.now() - timezone.timedelta(days=1)
        assignment.save(update_fields=["activated_at", "expires_at"])

        resolution = resolve_contest_access(self.contest)

        self.assertEqual("club_pass", resolution.source_type)
        self.assertEqual("annual_club_pass", resolution.tier_code)
