"""
Tests for ContestantViewSet's terminate/restart/reset REST actions - the API equivalents of the
classic terminate_contestant_calculator/restart_contestant_calculator/reset_contestant_calculator
views (views.py), added as part of migrating navigationtask_detail.html to the React SPA.

reset differs from restart only in that it does NOT call cancel_termination_request() afterwards
- see test_reset_leaves_termination_in_effect_but_restart_does_not.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Team
from display.utilities.calculator_termination_utilities import is_termination_requested, request_termination
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantCalculatorLifecycleRestActions(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Calculator Lifecycle Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Calculator Lifecycle Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="A", last_name="B", email="lifecycle@example.com")
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-LFC"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.manager = get_user_model().objects.create(email="lifecycle-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)

    def _url(self, action):
        return reverse(
            f"contestants-{action}",
            kwargs={
                "contest_pk": self.contest.pk,
                "navigationtask_pk": self.navigation_task.pk,
                "pk": self.contestant.pk,
            },
        )

    def test_terminate_calls_blocking_termination_and_succeeds(self, *args):
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination") as mock_terminate:
            response = self.client.post(self._url("terminate"))
        self.assertEqual(response.status_code, 200, response.content)
        mock_terminate.assert_called_once()

    def test_terminate_returns_409_on_timeout(self, *args):
        with patch(
            "display.models.contestant.Contestant.blocking_request_calculator_termination",
            side_effect=TimeoutError,
        ):
            response = self.client.post(self._url("terminate"))
        self.assertEqual(response.status_code, 409, response.content)

    def test_restart_resets_track_and_cancels_termination(self, *args):
        self.contestant.contestanttrack.score = 42
        self.contestant.contestanttrack.save(update_fields=["score"])
        request_termination(self.contestant.pk)

        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            response = self.client.post(self._url("restart"))

        self.assertEqual(response.status_code, 200, response.content)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, self.navigation_task.scorecard.initial_score)
        self.assertIsNone(is_termination_requested(self.contestant.pk))

    def test_restart_returns_409_on_timeout_without_resetting(self, *args):
        self.contestant.contestanttrack.score = 42
        self.contestant.contestanttrack.save(update_fields=["score"])

        with patch(
            "display.models.contestant.Contestant.blocking_request_calculator_termination",
            side_effect=TimeoutError,
        ):
            response = self.client.post(self._url("restart"))

        self.assertEqual(response.status_code, 409, response.content)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, 42)

    def test_reset_resets_track_but_leaves_termination_in_effect(self, *args):
        self.contestant.contestanttrack.score = 42
        self.contestant.contestanttrack.save(update_fields=["score"])
        request_termination(self.contestant.pk)

        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            response = self.client.post(self._url("reset"))

        self.assertEqual(response.status_code, 200, response.content)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, self.navigation_task.scorecard.initial_score)
        self.assertIsNotNone(is_termination_requested(self.contestant.pk))

    def test_reset_returns_409_on_timeout_without_resetting(self, *args):
        self.contestant.contestanttrack.score = 42
        self.contestant.contestanttrack.save(update_fields=["score"])

        with patch(
            "display.models.contestant.Contestant.blocking_request_calculator_termination",
            side_effect=TimeoutError,
        ):
            response = self.client.post(self._url("reset"))

        self.assertEqual(response.status_code, 409, response.content)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, 42)

    def test_reset_leaves_termination_in_effect_but_restart_does_not(self, *args):
        # Isolates exactly what each action does with the termination flag afterwards -
        # blocking_request_calculator_termination() is mocked out (it would itself set this
        # flag as a side effect of stopping the calculator).
        request_termination(self.contestant.pk)
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            self.client.post(self._url("reset"))
        self.assertIsNotNone(is_termination_requested(self.contestant.pk))

        request_termination(self.contestant.pk)
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            self.client.post(self._url("restart"))
        self.assertIsNone(is_termination_requested(self.contestant.pk))

    def test_actions_require_change_contest_permission(self, *args):
        viewer = get_user_model().objects.create(email="lifecycle-viewer@example.com")
        assign_perm("view_contest", viewer, self.contest)
        self.client.force_login(user=viewer)

        for action in ("terminate", "restart", "reset"):
            with patch(
                "display.models.contestant.Contestant.blocking_request_calculator_termination"
            ) as mock_terminate:
                response = self.client.post(self._url(action))
            self.assertEqual(response.status_code, 403, f"{action}: {response.content}")
            mock_terminate.assert_not_called()

    def test_actions_reject_get(self, *args):
        for action in ("terminate", "restart", "reset"):
            response = self.client.get(self._url(action))
            self.assertEqual(response.status_code, 405, f"{action}: {response.content}")
