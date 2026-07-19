from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from display.models import Contest, NavigationTask, Scorecard, Route, ContestTeam, Team, Crew, Person, Aeroplane
from display.services.capacity_enforcement import (
    assert_can_add_navigation_task,
    assert_can_register_team,
    assert_can_self_register_contestant,
)


@override_settings(
    DEFAULT_FREE_CONTESTANT_LIMIT=1,
    DEFAULT_FREE_TASK_LIMIT=1,
    ACCESS_ENFORCEMENT_MODE="enforce",
)
class TestCapacityEnforcement(TestCase):
    def setUp(self):
        self.contest = Contest.objects.create(
            name="Capacity Contest",
            time_zone="Europe/Oslo",
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
            location="60.0,11.0",
        )
        self.scorecard = Scorecard.get_originals().first() or Scorecard.objects.create(name="Test scorecard")
        self.route = Route.objects.create(name="Route")
        self.person = Person.objects.create(first_name="Pilot", last_name="One", email="pilot@example.com")
        self.team = Team.objects.create(
            crew=Crew.objects.create(member1=self.person),
            aeroplane=Aeroplane.objects.create(registration="LN-TEST"),
        )

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_blocks_navigation_task_creation_when_task_limit_reached(self, mock_resolve):
        mock_resolve.return_value = type("Resolution", (), {"task_limit": 1, "tasks_used": 1, "contestant_limit": None, "contestants_used": 0, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_add_navigation_task(self.contest)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_blocks_team_registration_when_contestant_limit_reached(self, mock_resolve):
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 1, "contestants_used": 1, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_register_team(self.contest)

    @patch("display.services.capacity_enforcement.resolve_contest_access")
    def test_self_registration_reuses_contestant_limit_rule(self, mock_resolve):
        navigation_task = NavigationTask.objects.create(
            name="Task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time="2026-03-01T09:00:00+00:00",
            finish_time="2026-03-01T17:00:00+00:00",
        )
        contest_team = ContestTeam.objects.create(contest=self.contest, team=self.team)
        mock_resolve.return_value = type("Resolution", (), {"task_limit": None, "tasks_used": 0, "contestant_limit": 1, "contestants_used": 1, "enforcement_mode": "enforce"})()

        with self.assertRaises(ValidationError):
            assert_can_self_register_contestant(navigation_task, contest_team)
