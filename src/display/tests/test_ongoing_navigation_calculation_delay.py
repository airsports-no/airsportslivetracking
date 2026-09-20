"""
REST-level tests for ContestViewSet.ongoing_navigation - GitHub issue 786: the mission
dashboard's "Live Now" ticker/ongoing-task list must not include a contestant (or a task with no
other visibly-live contestant) whose calculation_delay_minutes window hasn't elapsed yet.
"""

import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework.test import APITestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestOngoingNavigationRespectsCalculationDelay(APITestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Ongoing Navigation Delay Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5),
            location="60, 11",
        )
        self.user = get_user_model().objects.create(email="ongoing-delay@example.com")
        assign_perm("view_contest", self.user, self.contest)
        self.client.force_login(user=self.user)

    def _make_navigation_task(self, name, calculation_delay_minutes):
        route = Route.objects.create(name=f"Route {name}")
        return NavigationTask.create(
            name=name,
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=self.contest.start_time,
            finish_time=self.contest.finish_time,
            calculation_delay_minutes=calculation_delay_minutes,
        )

    def _make_contestant(self, navigation_task, number, tracker_start_minutes_ago, calculator_started=True):
        now = datetime.datetime.now(datetime.timezone.utc)
        crew = Crew.objects.create(
            member1=Person.objects.create(
                first_name="A", last_name=f"B{number}", email=f"ongoing-delay-{number}@example.com"
            )
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration=f"LN-OGD{number}"))
        contestant = Contestant.objects.create(
            team=team,
            navigation_task=navigation_task,
            takeoff_time=now - datetime.timedelta(minutes=tracker_start_minutes_ago),
            finished_by_time=now + datetime.timedelta(hours=1),
            tracker_start_time=now - datetime.timedelta(minutes=tracker_start_minutes_ago),
            tracker_device_id=f"ongoing-delay-device-{number}",
            contestant_number=number,
        )
        if calculator_started:
            contestant.contestanttrack.calculator_started = True
            contestant.contestanttrack.save(update_fields=["calculator_started"])
        return contestant

    def test_task_with_only_still_delayed_contestants_is_excluded_entirely(self, *args):
        navigation_task = self._make_navigation_task("Still delayed", calculation_delay_minutes=60)
        self._make_contestant(navigation_task, 1, tracker_start_minutes_ago=5)

        response = self.client.get(reverse("contests-ongoing-navigation"))

        self.assertEqual(response.status_code, 200, response.content)
        task_ids = [task["pk"] for task in response.data]
        self.assertNotIn(navigation_task.pk, task_ids)

    def test_task_appears_once_the_delay_has_elapsed(self, *args):
        navigation_task = self._make_navigation_task("Delay elapsed", calculation_delay_minutes=10)
        contestant = self._make_contestant(navigation_task, 1, tracker_start_minutes_ago=20)

        response = self.client.get(reverse("contests-ongoing-navigation"))

        self.assertEqual(response.status_code, 200, response.content)
        matching = [task for task in response.data if task["pk"] == navigation_task.pk]
        self.assertEqual(len(matching), 1)
        active_ids = [c["pk"] for c in matching[0]["active_contestants"]]
        self.assertIn(contestant.pk, active_ids)

    def test_task_appears_if_at_least_one_contestant_is_past_the_delay_even_if_another_is_not(self, *args):
        navigation_task = self._make_navigation_task("Mixed", calculation_delay_minutes=15)
        still_delayed = self._make_contestant(navigation_task, 1, tracker_start_minutes_ago=5)
        past_delay = self._make_contestant(navigation_task, 2, tracker_start_minutes_ago=20)

        response = self.client.get(reverse("contests-ongoing-navigation"))

        self.assertEqual(response.status_code, 200, response.content)
        matching = [task for task in response.data if task["pk"] == navigation_task.pk]
        self.assertEqual(len(matching), 1)
        active_ids = [c["pk"] for c in matching[0]["active_contestants"]]
        self.assertIn(past_delay.pk, active_ids)
        self.assertNotIn(still_delayed.pk, active_ids)
