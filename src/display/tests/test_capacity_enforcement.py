from unittest.mock import patch
import datetime

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from display.models import Contest, NavigationTask, Scorecard, Route, ContestTeam, Team, Crew, Person, Aeroplane, MyUser, ContestUsageLedger
from display.services.capacity_enforcement import (
    assert_can_add_navigation_task,
    assert_can_register_team,
    assert_can_self_register_contestant,
    assert_can_start_contestant,
)


@override_settings(
    DEFAULT_FREE_CONTESTANT_LIMIT=1,
    DEFAULT_FREE_TASK_LIMIT=1,
    ACCESS_ENFORCEMENT_MODE="enforce",
)
class TestCapacityEnforcement(TestCase):
    def setUp(self):
        self.owner_user = MyUser.objects.create(email="owner@example.com")
        self.owner_person = Person.objects.create(first_name="Owner", last_name="Pilot", email=self.owner_user.email)
        self.contest = Contest.objects.create(
            name="Capacity Contest",
            time_zone="Europe/Oslo",
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
            location="60.0,11.0",
            created_by=self.owner_user,
        )
        self.scorecard = Scorecard.get_originals().first() or Scorecard.objects.create(name="Test scorecard")
        self.route = Route.objects.create(name="Route")
        self.person = Person.objects.create(first_name="Pilot", last_name="One", email="pilot@example.com")
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=self.person),
            aeroplane=Aeroplane.objects.create(registration="LN-TEST"),
        )
        self.owner_team = Team.objects.create(
            crew=Crew.objects.create(member1=self.owner_person),
            aeroplane=Aeroplane.objects.create(registration="LN-OWNER"),
        )

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_blocks_navigation_task_creation_when_task_limit_reached(self, mock_resolve):
        mock_resolve.return_value = type("Resolution", (), {"task_limit": 1, "tasks_used": 1, "contestant_limit": None, "contestants_used": 0, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_add_navigation_task(self.contest)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_blocks_guest_team_registration_when_contestant_limit_reached(self, mock_resolve):
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 0, "contestants_used": 0, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_register_team(self.contest, self.team)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_owner_team_is_exempt_from_contestant_limit(self, mock_resolve):
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 0, "contestants_used": 0, "enforcement_mode": "enforce"})()

        resolution = assert_can_register_team(self.contest, self.owner_team)

        self.assertEqual(0, resolution.contestant_limit)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_self_registration_reuses_contestant_limit_rule_for_guests(self, mock_resolve):
        navigation_task = NavigationTask.objects.create(
            name="Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
        )
        contest_team = ContestTeam.objects.create(contest=self.contest, team=self.team)
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 0, "contestants_used": 0, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_self_register_contestant(navigation_task, contest_team)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_self_registration_allows_owner_team_when_limit_is_zero(self, mock_resolve):
        navigation_task = NavigationTask.objects.create(
            name="Owner Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
        )
        owner_contest_team = ContestTeam.objects.create(contest=self.contest, team=self.owner_team)
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 0, "contestants_used": 0, "enforcement_mode": "enforce"})()

        resolution = assert_can_self_register_contestant(navigation_task, owner_contest_team)

        self.assertEqual(0, resolution.contestant_limit)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_start_time_blocks_new_guest_team_when_contest_limit_reached(self, mock_resolve):
        navigation_task = NavigationTask.objects.create(
            name="Start Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
        )
        contestant = navigation_task.contestant_set.create(
            team=self.team,
            contestant_number=1,
            takeoff_time=datetime.datetime(2026, 3, 1, 9, 0, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 3, 1, 8, 50, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 3, 1, 11, 0, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        ContestUsageLedger.objects.create(
            contest=self.contest,
            team=Team.objects.create(
                crew=Crew.objects.create(member1=Person.objects.create(first_name="Other", last_name="Pilot", email="other@example.com")),
                aeroplane=Aeroplane.objects.create(registration="LN-OTHER"),
            ),
            kind=ContestUsageLedger.CONTEST_TEAM_STARTED,
        )
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 1, "contestants_used": 1, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_start_contestant(contestant)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_start_time_allows_same_team_recreation_when_slots_already_burned(self, mock_resolve):
        navigation_task = NavigationTask.objects.create(
            name="Restart Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
        )
        contestant = navigation_task.contestant_set.create(
            team=self.team,
            contestant_number=1,
            takeoff_time=datetime.datetime(2026, 3, 1, 9, 0, tzinfo=datetime.timezone.utc),
            tracker_start_time=datetime.datetime(2026, 3, 1, 8, 50, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2026, 3, 1, 11, 0, tzinfo=datetime.timezone.utc),
            air_speed=70,
            minutes_to_starting_point=5,
            wind_speed=0,
            wind_direction=0,
            gate_times={},
        )
        ContestUsageLedger.objects.create(
            contest=self.contest,
            team=self.team,
            contestant=contestant,
            kind=ContestUsageLedger.CONTEST_TEAM_STARTED,
            navigation_task=navigation_task,
        )
        ContestUsageLedger.objects.create(
            contest=self.contest,
            navigation_task=navigation_task,
            team=self.team,
            contestant=contestant,
            kind=ContestUsageLedger.TASK_TEAM_STARTED,
        )
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 1, "contestants_used": 1, "enforcement_mode": "enforce"})()

        resolution = assert_can_start_contestant(contestant)

        self.assertEqual(1, resolution.contestant_limit)
