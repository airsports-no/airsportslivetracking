"""
Tests for ContestantViewSet's terminate/restart/reset REST actions - the API equivalents of the
classic terminate_contestant_calculator/restart_contestant_calculator/reset_contestant_calculator
views (views.py), added as part of migrating navigationtask_detail.html to the React SPA.

reset differs from restart only in that it does NOT call cancel_termination_request() afterwards
- see test_reset_leaves_termination_in_effect_but_restart_does_not.
"""

import datetime
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase, APITransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    Aeroplane,
    Contest,
    ContestSummary,
    Contestant,
    Crew,
    NavigationTask,
    Person,
    Route,
    Team,
    TaskSummary,
    TeamTestScore,
)
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


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantRecalculateTrackRestAction(APITestCase):
    """ContestantViewSet.recalculate_track - REST equivalent of the classic
    revert_uploaded_gpx_track_for_contestant view ("Recalculate live track")."""

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Recalculate Track Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Recalculate Track Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="A", last_name="B", email="recalc-track@example.com")
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-RCT"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
        )
        self.manager = get_user_model().objects.create(email="recalc-track-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)
        self.url = reverse(
            "contestants-recalculate-track",
            kwargs={
                "contest_pk": self.contest.pk,
                "navigationtask_pk": self.navigation_task.pk,
                "pk": self.contestant.pk,
            },
        )

    @patch("display.viewsets.recalculate_live_data_for_contestant")
    def test_resets_track_and_dispatches_recalculation(self, mock_recalculate, *args):
        self.contestant.contestanttrack.score = 42
        self.contestant.contestanttrack.save(update_fields=["score"])

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200, response.content)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, self.navigation_task.scorecard.initial_score)
        mock_recalculate.apply_async.assert_called_once_with((self.contestant.pk,))

    @patch("display.viewsets.is_calculator_running", return_value=True)
    @patch("display.viewsets.recalculate_live_data_for_contestant")
    def test_refuses_while_calculator_is_running(self, mock_recalculate, _mock_running, *args):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 409, response.content)
        mock_recalculate.apply_async.assert_not_called()


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantRecalculateWithStartTimeRestAction(APITransactionTestCase):
    """ContestantViewSet.recalculate_with_start_time - REST equivalent of the classic
    ContestantRecalculateWithStartTimeView. Replaces the contestant with a new one (new pk)
    sharing the same team/positions/uploaded track but a new starting-point-derived schedule.

    Uses APITransactionTestCase (not APITestCase) so the action's transaction.on_commit()
    callback (dispatching the recalculation task) actually fires - APITestCase/TestCase wrap
    each test in an outer atomic block that's rolled back, not committed, so on_commit hooks
    registered inside it never run.
    """

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Recalculate Start Time Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Recalculate Start Time Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
            minutes_to_landing=10,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="A", last_name="B", email="recalc-start@example.com")
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-RCS"))
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="test_device",
            contestant_number=1,
            minutes_to_starting_point=8,
        )
        self.manager = get_user_model().objects.create(email="recalc-start-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)
        self.url = reverse(
            "contestants-recalculate-with-start-time",
            kwargs={
                "contest_pk": self.contest.pk,
                "navigationtask_pk": self.navigation_task.pk,
                "pk": self.contestant.pk,
            },
        )

    @patch("display.viewsets.recalculate_existing_positions")
    @patch(
        "display.models.contestant.Contestant.flight_duration",
        new_callable=PropertyMock,
        return_value=datetime.timedelta(hours=1),
    )
    def test_creates_new_contestant_with_derived_schedule_and_moves_positions(
        self, _mock_flight_duration, mock_recalculate, *args
    ):
        from display.models.contestant_utility_models import ContestantReceivedPosition

        old_pk = self.contestant.pk
        position_time = self.navigation_task.start_time + datetime.timedelta(minutes=5)
        ContestantReceivedPosition.objects.create(
            contestant=self.contestant, time=position_time, latitude=60.0, longitude=11.0
        )
        starting_point_time = self.navigation_task.start_time + datetime.timedelta(hours=3)

        response = self.client.post(
            self.url, data={"starting_point_time": starting_point_time.isoformat()}, format="json"
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(Contestant.objects.filter(pk=old_pk).exists())
        new_pk = response.data["id"]
        self.assertNotEqual(new_pk, old_pk)

        new_contestant = Contestant.objects.get(pk=new_pk)
        self.assertEqual(new_contestant.contestant_number, 1)
        self.assertEqual(
            new_contestant.takeoff_time,
            starting_point_time - datetime.timedelta(minutes=self.navigation_task.minutes_to_starting_point),
        )
        self.assertEqual(new_contestant.finished_by_time, starting_point_time + datetime.timedelta(hours=1))
        self.assertEqual(new_contestant.contestantreceivedposition_set.count(), 1)
        self.assertEqual(new_contestant.contestantreceivedposition_set.first().time, position_time)
        mock_recalculate.delay.assert_called_once_with(new_pk)

    def test_requires_starting_point_time(self, *args):
        response = self.client.post(self.url, data={}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Contestant.objects.filter(pk=self.contestant.pk).exists())

    @patch("display.viewsets.recalculate_existing_positions")
    @patch(
        "display.models.contestant.Contestant.flight_duration",
        new_callable=PropertyMock,
        return_value=datetime.timedelta(hours=1),
    )
    def test_deleting_old_contestant_clears_its_team_test_score(self, _mock_flight_duration, mock_recalculate, *args):
        # recalculate_with_start_time deletes the old contestant (a new one, with a new pk,
        # takes over its positions/track) - before the pre_delete(Contestant) signal added for
        # deleting a contestant outright, this was actually the worst case of that bug: the old
        # contestant's score for this navigation task's TaskTest would survive forever as an
        # orphan, since nothing about "replace this contestant" ever touched TeamTestScore.
        team = self.contestant.team
        self.contestant.contestanttrack.update_score(77)
        task_test = self.navigation_task.tasktest
        self.assertEqual(TeamTestScore.objects.get(task_test=task_test, team=team).points, 77)
        self.assertEqual(TaskSummary.objects.get(task=task_test.task, team=team).points, 77)
        self.assertEqual(ContestSummary.objects.get(contest=self.contest, team=team).points, 77)

        starting_point_time = self.navigation_task.start_time + datetime.timedelta(hours=3)
        response = self.client.post(
            self.url, data={"starting_point_time": starting_point_time.isoformat()}, format="json"
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(TeamTestScore.objects.filter(task_test=task_test, team=team).exists())
        self.assertEqual(TaskSummary.objects.get(task=task_test.task, team=team).points, 0)
        self.assertEqual(ContestSummary.objects.get(contest=self.contest, team=team).points, 0)
