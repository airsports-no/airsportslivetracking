import datetime
from unittest.mock import patch

from django.core.exceptions import ValidationError
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
    ContestTeam,
    TRACKING_COPILOT,
    TRACKING_PILOT,
)
from display.utilities.tracking_definitions import TrackingService
from utilities.mock_utilities import TraccarMock

TRACKER_NAME = "tracker"


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestContestantValidation(TransactionTestCase):
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
        self.initial_contestant = Contestant.objects.create(
            team=self.team,
            tracking_device=TRACKING_DEVICE,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 1, 9, 30, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
        )

    def test_overlapping_contestant_after(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "[\"The tracker 'tracker' is in use by other contestants for the intervals: [(<NavigationTask: NavigationTask: 2020-01-01>, '2020-01-01T11:00:00+00:00', '2020-01-01T12:00:00+00:00')]\"]",
        ):
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
            )

    def test_overlapping_contestant_before(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "[\"The tracker 'tracker' is in use by other contestants for the intervals: [(<NavigationTask: NavigationTask: 2020-01-01>, '2020-01-01T09:30:00+00:00', '2020-01-01T11:00:00+00:00')]\"]",
        ):
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 1, 9, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
            )

    def test_overlapping_contestant_inside(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "\"The tracker 'tracker' is in use by other contestants for the intervals: [(<NavigationTask: NavigationTask: 2020-01-01>, '2020-01-01T11:00:00+00:00', '2020-01-01T11:30:00+00:00')]\"",
        ):
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 1, 11, 30, tzinfo=datetime.timezone.utc),
            )

    def test_overlapping_contestant_outside(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "[\"The tracker 'tracker' is in use by other contestants for the intervals: [(<NavigationTask: NavigationTask: 2020-01-01>, '2020-01-01T09:30:00+00:00', '2020-01-01T12:00:00+00:00')]\"]",
        ):
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 1, 9, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
            )

    def test_no_overlap(self, *args):
        try:
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 1, 13, 30, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 1, 16, tzinfo=datetime.timezone.utc),
            )
        except ValidationError:
            self.fail(" There is no overlap so there should be no validation error")

    def test_take_off_before_tracking(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "Tracker start time '2020-01-02 14:00:00+00:00' is after takeoff time '2020-01-02 13:30:00+00:00' for contestant number 2",
        ):
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 2, 13, 30, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 2, 14, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 2, 16, tzinfo=datetime.timezone.utc),
            )

    def test_finish_before_takeoff(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "Takeoff time '2020-01-02 13:30:00+00:00' is after finished by time '2020-01-02 13:15:00+00:00' for contestant number 2",
        ):
            Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 2, 13, 30, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 2, 13, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 2, 13, 15, tzinfo=datetime.timezone.utc),
            )

    def test_calculator_started_nothing_modified(self, *args):
        contestant = Contestant.objects.create(
            team=self.team,
            navigation_task=self.navigation_task,
            tracking_device=TRACKING_DEVICE,
            takeoff_time=datetime.datetime(2020, 1, 2, 13, 30, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 2, 13, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 2, 16, tzinfo=datetime.timezone.utc),
        )
        contestant.contestanttrack.calculator_started = True
        contestant.save()
        # Second save should detect that nothing vital has changed and not throw an exception
        contestant.takeoff_time = contestant.takeoff_time.replace(hour=contestant.takeoff_time.hour)
        contestant.save()

    def test_calculator_started_modified_takeoff_time(self, *args):
        with self.assertRaisesMessage(
            ValidationError,
            "Calculator has started for 2 - Mister Pilot in registration, it is not possible to change takeoff time",
        ):
            contestant = Contestant.objects.create(
                team=self.team,
                navigation_task=self.navigation_task,
                tracking_device=TRACKING_DEVICE,
                takeoff_time=datetime.datetime(2020, 1, 2, 13, 30, tzinfo=datetime.timezone.utc),
                contestant_number=2,
                tracker_device_id=TRACKER_NAME,
                tracker_start_time=datetime.datetime(2020, 1, 2, 13, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 2, 16, tzinfo=datetime.timezone.utc),
            )
            contestant.contestanttrack.calculator_started = True
            contestant.contestanttrack.save()
            # Second save should detect that nothing vital has changed and not throw an exception
            contestant.takeoff_time = contestant.takeoff_time.replace(hour=contestant.takeoff_time.hour + 1)
            contestant.save()


class TestGetContestantForDevice(TransactionTestCase):
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
        double_crew = Crew.objects.create(
            member1=Person.objects.get(first_name="Mister", last_name="Pilot"),
            member2=Person.objects.create(first_name="Mister1", last_name="Pilot2", email="test@test.com"),
        )
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        self.double_team = Team.objects.create(crew=double_crew, aeroplane=aeroplane)
        self.contestant_tracking_device = Contestant.objects.create(
            team=self.team,
            tracking_device=TRACKING_DEVICE,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            contestant_number=1,
            tracker_device_id=TRACKER_NAME,
            tracker_start_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 11, tzinfo=datetime.timezone.utc),
        )

        self.contestant_pilot_device = Contestant.objects.create(
            team=self.team,
            tracking_device=TRACKING_PILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
            contestant_number=2,
            tracker_device_id="",
            tracker_start_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 13, tzinfo=datetime.timezone.utc),
        )
        self.contestant_copilot_device = Contestant.objects.create(
            team=self.double_team,
            tracking_device=TRACKING_COPILOT,
            navigation_task=self.navigation_task,
            takeoff_time=datetime.datetime(2020, 1, 1, 14, tzinfo=datetime.timezone.utc),
            contestant_number=3,
            tracker_device_id="",
            tracker_start_time=datetime.datetime(2020, 1, 1, 14, tzinfo=datetime.timezone.utc),
            finished_by_time=datetime.datetime(2020, 1, 1, 15, tzinfo=datetime.timezone.utc),
        )

    def test_get_tracking_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, TRACKER_NAME, datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc)
        )
        self.assertEqual(self.contestant_tracking_device, contestant)

    def test_get_no_pilot_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR,
            self.team.crew.member1.app_tracking_id,
            datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(None, contestant)

    def test_get_no_copilot_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR,
            self.double_team.crew.member2.app_tracking_id,
            datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(None, contestant)

    def test_get_tracking_pilot(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR,
            self.team.crew.member1.app_tracking_id,
            datetime.datetime(2020, 1, 1, 12, 3, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(self.contestant_pilot_device, contestant)

    def test_get_pilot_no_tracking_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, TRACKER_NAME, datetime.datetime(2020, 1, 1, 12, 3, tzinfo=datetime.timezone.utc)
        )
        self.assertEqual(None, contestant)

    def test_get_pilot_no_copilot_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR,
            self.double_team.crew.member2.app_tracking_id,
            datetime.datetime(2020, 1, 1, 12, 3, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(None, contestant)

    def test_get_tracking_copilot(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR,
            self.double_team.crew.member2.app_tracking_id,
            datetime.datetime(2020, 1, 1, 14, 5, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(self.contestant_copilot_device, contestant)

    def test_get_copilot_no_tracking_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR, TRACKER_NAME, datetime.datetime(2020, 1, 1, 14, 3, tzinfo=datetime.timezone.utc)
        )
        self.assertEqual(None, contestant)

    def test_get_copilot_no_pilot_device(self):
        contestant, simulator = Contestant.get_contestant_for_device_at_time(
            TrackingService.TRACCAR,
            self.team.crew.member1.app_tracking_id,
            datetime.datetime(2020, 1, 1, 14, 3, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(None, contestant)

    def test_create_device_contest_team_without_tracking_id(self):
        with self.assertRaises(ValidationError):
            ContestTeam.objects.create(
                team=self.team, tracking_device=TRACKING_DEVICE, tracker_device_id="", contest=self.contest
            )
        ContestTeam.objects.create(
            team=self.team, tracking_device=TRACKING_DEVICE, tracker_device_id="1", contest=self.contest
        )

    def test_create_copilot_contest_team_without_copilot(self):
        with self.assertRaises(ValidationError):
            ContestTeam.objects.create(team=self.team, tracking_device=TRACKING_COPILOT, contest=self.contest)
        ContestTeam.objects.create(team=self.double_team, tracking_device=TRACKING_COPILOT, contest=self.contest)
