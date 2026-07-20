import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

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
)
from display.services.access_resolver import resolve_contest_access
from display.services.token_assignment import assign_token_to_contest, revert_token_assignment_for_support


class TestTokenAssignment(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="token-owner@example.com")
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
            task_limit=3,
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
        self.assertEqual(1, resolution.tasks_used)
        self.assertEqual(1, ContestUsageLedger.objects.filter(contest=self.contest, kind=ContestUsageLedger.CONTESTANT_STARTED).count())
        self.assertEqual(1, ContestUsageLedger.objects.filter(contest=self.contest, kind=ContestUsageLedger.TASK_STARTED).count())

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
