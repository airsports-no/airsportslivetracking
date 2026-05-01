
import datetime
from unittest.mock import patch
from django.test import TransactionTestCase
from display.models import Contest, Contestant, Route, NavigationTask, Aeroplane, Crew, Team, Person, TRACKING_DEVICE
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from utilities.mock_utilities import TraccarMock

@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestSignals(TransactionTestCase):
    def test_save_contest_with_colliding_contestant_id(self, *args):
        # Create a contest. It will get ID 1.
        contest = Contest.objects.create(
            name="TestContest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
        )
        self.assertEqual(contest.pk, 1)

        # Create a contestant. It will also get ID 1 (in its own table).
        route = Route.objects.create(name="Route")
        navigation_task = NavigationTask.create(
            name="NavigationTask",
            original_scorecard=get_default_scorecard(),
            start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            route=route,
            contest=contest,
        )
        aeroplane = Aeroplane.objects.create(registration="registration")
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        contestant = Contestant.objects.create(
            team=team,
            tracking_device=TRACKING_DEVICE,
            navigation_task=navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_device_id="tracker",
            tracker_start_time=datetime.datetime(2020, 1, 1, 9, 30, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(contestant.pk, 1)

        # Now save the contest again. 
        # Before the fix, this would trigger the pre_save signal,
        # which would find Contestant(pk=1) and then crash trying to access 
        # starting_point_time on the Contest object.
        contest.name = "Updated TestContest"
        try:
            contest.save()
        except AttributeError as e:
            self.fail(f"Contest.save() raised AttributeError: {e}")
