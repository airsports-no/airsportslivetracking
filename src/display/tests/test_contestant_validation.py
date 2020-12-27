import datetime

from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import NavigationTask, Contest, Route, Contestant, Aeroplane, Crew, Team, Person

TRACKER_NAME = "tracker"


class TestContestantValidation(TransactionTestCase):
    def setUp(self):
        self.contest = Contest.objects.create(name="TestContest", start_time=datetime.datetime.utcnow(),
                                              finish_time=datetime.datetime.utcnow())
        route = Route.objects.create(name="Route")
        self.navigation_task = NavigationTask.objects.create(name="NavigationTask",
                                                             start_time=datetime.datetime.utcnow(),
                                                             finish_time=datetime.datetime.utcnow(),
                                                             route=route, contest=self.contest)
        aeroplane = Aeroplane.objects.create(registration="registration")
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Mister", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=aeroplane)
        self.initial_contestant = Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                                            navigation_task=self.navigation_task,
                                                            takeoff_time=datetime.datetime(2020, 1, 1, 10,
                                                                                           tzinfo=datetime.timezone.utc),
                                                            contestant_number=1, tracker_device_id=TRACKER_NAME,
                                                            tracker_start_time=datetime.datetime(2020, 1, 1, 9, 30,
                                                                                                 tzinfo=datetime.timezone.utc),
                                                            finished_by_time=datetime.datetime(2020, 1, 1, 12,
                                                                                               tzinfo=datetime.timezone.utc))

    def test_overlapping_contestant_after(self):
        with self.assertRaisesMessage(ValidationError,
                                      "The tracker 'tracker' is in use by other contestants for the intervals: [('2020-01-01T11:00:00+00:00', '2020-01-01T12:00:00+00:00')"):
            Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                      navigation_task=self.navigation_task,
                                      takeoff_time=datetime.datetime(2020, 1, 1, 10,
                                                                     tzinfo=datetime.timezone.utc),
                                      contestant_number=2, tracker_device_id=TRACKER_NAME,
                                      tracker_start_time=datetime.datetime(2020, 1, 1, 11,
                                                                           tzinfo=datetime.timezone.utc),
                                      finished_by_time=datetime.datetime(2020, 1, 1, 13,
                                                                         tzinfo=datetime.timezone.utc))

    def test_overlapping_contestant_before(self):
        with self.assertRaisesMessage(ValidationError,
                                      "The tracker 'tracker' is in use by other contestants for the intervals: [('2020-01-01T09:30:00+00:00', '2020-01-01T11:00:00+00:00')"):
            Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                      navigation_task=self.navigation_task,
                                      takeoff_time=datetime.datetime(2020, 1, 1, 10,
                                                                     tzinfo=datetime.timezone.utc),
                                      contestant_number=2, tracker_device_id=TRACKER_NAME,
                                      tracker_start_time=datetime.datetime(2020, 1, 1, 9,
                                                                           tzinfo=datetime.timezone.utc),
                                      finished_by_time=datetime.datetime(2020, 1, 1, 11,
                                                                         tzinfo=datetime.timezone.utc))

    def test_overlapping_contestant_inside(self):
        with self.assertRaisesMessage(ValidationError,
                                      "The tracker 'tracker' is in use by other contestants for the intervals: [('2020-01-01T11:00:00+00:00', '2020-01-01T11:30:00+00:00')"):
            Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                      navigation_task=self.navigation_task,
                                      takeoff_time=datetime.datetime(2020, 1, 1, 11,
                                                                     tzinfo=datetime.timezone.utc),
                                      contestant_number=2, tracker_device_id=TRACKER_NAME,
                                      tracker_start_time=datetime.datetime(2020, 1, 1, 11,
                                                                           tzinfo=datetime.timezone.utc),
                                      finished_by_time=datetime.datetime(2020, 1, 1, 11, 30,
                                                                         tzinfo=datetime.timezone.utc))

    def test_overlapping_contestant_outside(self):
        with self.assertRaisesMessage(ValidationError,
                                      "The tracker 'tracker' is in use by other contestants for the intervals: [('2020-01-01T09:30:00+00:00', '2020-01-01T12:00:00+00:00')"):
            Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                      navigation_task=self.navigation_task,
                                      takeoff_time=datetime.datetime(2020, 1, 1, 10,
                                                                     tzinfo=datetime.timezone.utc),
                                      contestant_number=2, tracker_device_id=TRACKER_NAME,
                                      tracker_start_time=datetime.datetime(2020, 1, 1, 9,
                                                                           tzinfo=datetime.timezone.utc),
                                      finished_by_time=datetime.datetime(2020, 1, 1, 13,
                                                                         tzinfo=datetime.timezone.utc))

    def test_no_overlap(self):
        try:
            Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                      navigation_task=self.navigation_task,
                                      takeoff_time=datetime.datetime(2020, 1, 1, 13, 30,
                                                                     tzinfo=datetime.timezone.utc),
                                      contestant_number=2, tracker_device_id=TRACKER_NAME,
                                      tracker_start_time=datetime.datetime(2020, 1, 1, 13,
                                                                           tzinfo=datetime.timezone.utc),
                                      finished_by_time=datetime.datetime(2020, 1, 1, 16,
                                                                         tzinfo=datetime.timezone.utc))
        except ValidationError:
            self.fail(" There is no overlap so there should be no validation error")

    def test_take_off_before_tracking(self):
        with self.assertRaisesMessage(ValidationError,
                                      "Tracker start time '2020-01-02 14:00:00+00:00' is after takeoff time '2020-01-02 13:30:00+00:00' for contestant number 2"):
            Contestant.objects.create(team=self.team, scorecard=get_default_scorecard(),
                                      navigation_task=self.navigation_task,
                                      takeoff_time=datetime.datetime(2020, 1, 2, 13, 30,
                                                                     tzinfo=datetime.timezone.utc),
                                      contestant_number=2, tracker_device_id=TRACKER_NAME,
                                      tracker_start_time=datetime.datetime(2020, 1, 2, 14,
                                                                           tzinfo=datetime.timezone.utc),
                                      finished_by_time=datetime.datetime(2020, 1, 2, 16,
                                                                         tzinfo=datetime.timezone.utc))
