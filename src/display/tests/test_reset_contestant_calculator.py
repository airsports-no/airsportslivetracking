"""
Regression/behavioural tests for the "Reset Calculator" action added alongside "Restart
Calculator": both clear the contestant's track/score/results-service state the same way
(Contestant.reset_track_and_score()), but only Restart re-arms the calculator to start again
on the next received position (by cancelling the termination request). Reset deliberately
leaves termination in effect, so a cleared contestant stays inert until explicitly restarted.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, ContestTeam, Crew, NavigationTask, Person, Route, Team
from display.utilities.calculator_termination_utilities import is_termination_requested, request_termination
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestResetContestantCalculator(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Reset Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        now = datetime.datetime.now(datetime.timezone.utc)
        self.navigation_task = NavigationTask.create(
            name="Reset Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="A", last_name="B", email="reset@example.com")
        )
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-RST"))
        ContestTeam.objects.create(contest=self.contest, team=self.team, air_speed=70)
        self.contestant = Contestant.objects.create(
            team=self.team,
            navigation_task=self.navigation_task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="reset_test_device",
            contestant_number=1,
        )

        self.manager = get_user_model().objects.create(email="reset-manager@example.com")
        assign_perm("view_contest", self.manager, self.contest)
        assign_perm("change_contest", self.manager, self.contest)
        self.client.force_login(user=self.manager)

    def test_reset_leaves_termination_in_effect(self, *args):
        # Unlike restart, reset must NOT re-arm the calculator - a fresh position arriving
        # right after a reset should not be picked up until an explicit restart. The real
        # blocking_request_calculator_termination() would itself set this flag as a side
        # effect of stopping the calculator - mocked out here, so set it directly to isolate
        # what the view does with it AFTERWARDS (cancel it, or leave it).
        request_termination(self.contestant.pk)

        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            response = self.client.post(reverse("contestant_reset_calculator", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(is_termination_requested(self.contestant.pk))

    def test_reset_clears_track_and_score(self, *args):
        self.contestant.contestanttrack.score = 42
        self.contestant.contestanttrack.save(update_fields=["score"])

        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            response = self.client.post(reverse("contestant_reset_calculator", kwargs={"pk": self.contestant.pk}))

        self.assertEqual(response.status_code, 302)
        self.contestant.contestanttrack.refresh_from_db()
        self.assertEqual(self.contestant.contestanttrack.score, self.navigation_task.scorecard.initial_score)
        self.assertEqual(self.contestant.contestanttrack.current_state, "Waiting...")

    def test_restart_cancels_termination_but_reset_does_not(self, *args):
        # blocking_request_calculator_termination() is mocked out (it would itself set this
        # flag as a side effect of stopping the calculator) so the termination flag is set
        # directly instead, isolating exactly what each view does with it afterwards.
        request_termination(self.contestant.pk)
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            self.client.post(reverse("contestant_reset_calculator", kwargs={"pk": self.contestant.pk}))
        self.assertIsNotNone(is_termination_requested(self.contestant.pk))

        request_termination(self.contestant.pk)
        with patch("display.models.contestant.Contestant.blocking_request_calculator_termination"):
            self.client.post(reverse("contestant_restart_calculator", kwargs={"pk": self.contestant.pk}))
        self.assertIsNone(is_termination_requested(self.contestant.pk))
