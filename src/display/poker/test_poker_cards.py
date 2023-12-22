from unittest.mock import patch

import datetime
from django.test import TestCase

from display.default_scorecards.default_scorecard_airsports import get_default_scorecard
from display.models import Contestant, Contest, Route, NavigationTask, Aeroplane, Crew, Person, Team, PlayingCard
from display.tests.test_contestant_validation import TRACKER_NAME
from display.utilities.tracking_definitions import TRACKING_DEVICE
from utilities.mock_utilities import TraccarMock


class TestPlayingCards(TestCase):
    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        self.contest = Contest.objects.create(
            name="TestContest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.create(
            name="NavigationTask",
            original_scorecard=get_default_scorecard(),
            start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            route=route,
            contest=self.contest,
        )
        aeroplane = Aeroplane.objects.create(registration="registration")
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        self.contestant = Contestant.objects.create(
            team=self.team,
            tracking_device=TRACKING_DEVICE,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 1, 9, 30, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )

    def test_evaluate_hand(self):
        PlayingCard.objects.create(contestant=self.contestant, card="9h")
        PlayingCard.objects.create(contestant=self.contestant, card="9s")
        score, hand_type = PlayingCard.evaluate_hand(self.contestant)
        self.assertEqual(17235968, score)
        self.assertEqual("Pair", hand_type)
