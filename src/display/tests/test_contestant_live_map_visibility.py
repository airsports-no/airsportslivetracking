"""
Tests for Contestant.is_currently_visible_on_live_map - GitHub issue 786: the live flights
ticker and ongoing-navigation-task list must not tell spectators a contestant can be watched
before its delayed position data (calculation_delay_minutes) has actually started appearing on
the live map.
"""

import datetime
from unittest.mock import patch

from django.test import TestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantIsCurrentlyVisibleOnLiveMap(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="Live Visibility Contest",
            start_time=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1),
            finish_time=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5),
            location="60, 11",
        )
        route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.create(
            name="Live Visibility Task",
            original_scorecard=get_default_scorecard(),
            route=route,
            contest=self.contest,
            start_time=self.contest.start_time,
            finish_time=self.contest.finish_time,
            calculation_delay_minutes=15,
        )
        crew = Crew.objects.create(
            member1=Person.objects.create(first_name="A", last_name="B", email="live-visibility@example.com")
        )
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-VIS"))
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            team=team,
            navigation_task=self.navigation_task,
            takeoff_time=now - datetime.timedelta(minutes=20),
            finished_by_time=now + datetime.timedelta(hours=1),
            tracker_start_time=now - datetime.timedelta(minutes=20),
            tracker_device_id="live-vis-device",
            contestant_number=1,
        )

    def test_not_visible_before_calculator_has_started(self, *args):
        self.assertFalse(self.contestant.contestanttrack.calculator_started)
        self.assertFalse(self.contestant.is_currently_visible_on_live_map())

    def test_not_visible_within_the_calculation_delay_window(self, *args):
        # tracker_start_time was 20 minutes ago - a delay longer than that (60 minutes) means
        # the delay window hasn't elapsed yet, so nothing should be visible on the map yet.
        self.navigation_task.calculation_delay_minutes = 60
        self.navigation_task.save(update_fields=["calculation_delay_minutes"])
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.save(update_fields=["calculator_started"])

        self.assertFalse(self.contestant.is_currently_visible_on_live_map())

    def test_visible_once_the_calculation_delay_has_elapsed(self, *args):
        # tracker_start_time was 20 minutes ago and calculation_delay_minutes is 15 - the delay
        # has elapsed, so delayed position data should have started appearing on the map.
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.save(update_fields=["calculator_started"])

        self.assertTrue(self.contestant.is_currently_visible_on_live_map())

    def test_not_visible_once_the_calculator_has_finished(self, *args):
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.calculator_finished = True
        self.contestant.contestanttrack.save(update_fields=["calculator_started", "calculator_finished"])

        self.assertFalse(self.contestant.is_currently_visible_on_live_map())

    def test_not_visible_once_past_finished_by_time(self, *args):
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.save(update_fields=["calculator_started"])
        self.contestant.finished_by_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            minutes=1
        )
        self.contestant.save(update_fields=["finished_by_time"])

        self.assertFalse(self.contestant.is_currently_visible_on_live_map())

    def test_visible_immediately_when_there_is_no_configured_delay(self, *args):
        # tracker_start_time (set in setUp) was 20 minutes ago - with no delay configured at
        # all, that's already well past the (zero-length) delay window.
        self.navigation_task.calculation_delay_minutes = 0
        self.navigation_task.save(update_fields=["calculation_delay_minutes"])
        self.contestant.contestanttrack.calculator_started = True
        self.contestant.contestanttrack.save(update_fields=["calculator_started"])

        self.assertTrue(self.contestant.is_currently_visible_on_live_map())
