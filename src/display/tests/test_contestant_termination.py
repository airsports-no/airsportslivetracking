import datetime
from unittest.mock import patch

from django.test import TransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import (
    NavigationTask,
    Contest,
    Route,
    Contestant,
    Aeroplane,
    Crew,
    Team,
    Person,
    TRACKING_DEVICE,
    TRACKING_PILOT,
    TRACKING_COPILOT,
)
from utilities.mock_utilities import TraccarMock

TRACKER_NAME = "tracker"


class TestContestantTermination(TransactionTestCase):
    def setUp(self):
        # Pythonic way to handle persistent mocks in TestCase without modifying every method signature
        self.traccar_patcher = patch("display.utilities.traccar_factory.Traccar")
        self.mock_traccar_class = self.traccar_patcher.start()
        self.mock_traccar_class.create_from_configuration.return_value = TraccarMock

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
        self.person1 = Person.objects.create(first_name="Mister", last_name="Pilot", email="pilot@test.com")
        self.person2 = Person.objects.create(first_name="Mister", last_name="Copilot", email="copilot@test.com")

        crew1 = Crew.objects.create(member1=self.person1)
        self.team1 = Team.objects.create(crew=crew1, aeroplane=aeroplane)

        crew2 = Crew.objects.create(member1=self.person2)
        self.team2 = Team.objects.create(crew=crew2, aeroplane=aeroplane)

        # Team with both
        crew3 = Crew.objects.create(member1=self.person1, member2=self.person2)
        self.team3 = Team.objects.create(crew=crew3, aeroplane=aeroplane)

    def tearDown(self):
        self.traccar_patcher.stop()

    def test_terminate_physical_tracker_overlap(self):
        # Old contestant running from 10:00 to 12:00
        old_contestant = Contestant.objects.create(
            team=self.team1,
            tracking_device=TRACKING_DEVICE,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )

        # New contestant starts at 11:00 with same tracker
        new_contestant = Contestant.objects.create(
            team=self.team2,
            tracking_device=TRACKING_DEVICE,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
        )

        # Trigger termination at 11:00
        termination_time = datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc)
        new_contestant.terminate_concurrent_contestants(termination_time)

        old_contestant.refresh_from_db()
        self.assertEqual(old_contestant.finished_by_time, termination_time)

    def test_terminate_app_tracker_pilot_overlap(self):
        # Old contestant: person1 is pilot, using app tracking
        old_contestant = Contestant.objects.create(
            team=self.team1,
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )

        # New contestant: person1 is pilot (in team3), using app tracking
        new_contestant = Contestant.objects.create(
            team=self.team3,  # crew3 has person1 as member1
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
        )

        termination_time = datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc)
        new_contestant.terminate_concurrent_contestants(termination_time)

        old_contestant.refresh_from_db()
        self.assertEqual(old_contestant.finished_by_time, termination_time)

    def test_terminate_app_tracker_copilot_overlap(self):
        # Old contestant: person2 is pilot (in team2), using app tracking
        # Wait, tracking_device=TRACKING_PILOT uses member1's ID.
        old_contestant = Contestant.objects.create(
            team=self.team2,  # crew2 has person2 as member1
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )

        # New contestant: person2 is copilot (in team3), using app tracking (TRACKING_COPILOT)
        new_contestant = Contestant.objects.create(
            team=self.team3,  # crew3 has person2 as member2
            tracking_device=TRACKING_COPILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
        )

        termination_time = datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc)
        new_contestant.terminate_concurrent_contestants(termination_time)

        old_contestant.refresh_from_db()
        self.assertEqual(old_contestant.finished_by_time, termination_time)

    def test_no_overlap_different_trackers(self):
        # Old contestant: person1 using app
        old_contestant = Contestant.objects.create(
            team=self.team1,
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )

        # New contestant: person2 using app
        new_contestant = Contestant.objects.create(
            team=self.team2,
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
        )

        termination_time = datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc)
        new_contestant.terminate_concurrent_contestants(termination_time)

        old_contestant.refresh_from_db()
        # Should NOT satisfy termination criteria because IDs are different
        self.assertEqual(
            old_contestant.finished_by_time, datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc)
        )

    def test_no_overlap_time_disjoint(self):
        # Old contestant finished at 10:59
        old_contestant = Contestant.objects.create(
            team=self.team1,
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 10, 59, tzinfo=datetime.timezone.utc),
        )

        # New contestant starts at 11:00
        new_contestant = Contestant.objects.create(
            team=self.team1,
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
        )

        termination_time = datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc)
        new_contestant.terminate_concurrent_contestants(termination_time)

        old_contestant.refresh_from_db()
        # Should NOT change because finished_by_time < termination_time
        self.assertEqual(
            old_contestant.finished_by_time, datetime.datetime(2020, 1, 1, 10, 59, tzinfo=datetime.timezone.utc)
        )
