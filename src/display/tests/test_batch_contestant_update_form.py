import datetime
from unittest.mock import patch

from django.test import TransactionTestCase

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.forms import BatchContestantUpdateForm
from display.models import Aeroplane, Contest, Contestant, Crew, NavigationTask, Person, Route, Team, TRACKING_DEVICE
from display.utilities.calculator_running_utilities import calculator_dispatch_pending, calculator_is_alive
from utilities.mock_utilities import TraccarMock

TRACKER_NAME = "tracker"


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestBatchContestantUpdateForm(TransactionTestCase):
    """
    Regression test for GH #29: the batch time-shift tool used to permanently exclude any
    contestant whose calculator had ever started (calculator_started never reverts to False on
    a normal finish), which blocked fixing a wrong takeoff time for any contestant who had
    already flown - not just ones currently flying.
    """

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

        def make_contestant(number, calculator_started, current_time=None):
            contestant = Contestant.objects.create(
                team=self.team,
                tracking_device=TRACKING_DEVICE,
                navigation_task=self.navigation_task,
                takeoff_time=datetime.datetime(2020, 1, 1, 10, tzinfo=datetime.timezone.utc),
                contestant_number=number,
                tracker_device_id=f"{TRACKER_NAME}{number}",
                tracker_start_time=datetime.datetime(2020, 1, 1, 9, 30, tzinfo=datetime.timezone.utc),
                finished_by_time=datetime.datetime(2020, 1, 1, 12, tzinfo=datetime.timezone.utc),
            )
            if calculator_started:
                contestant.contestanttrack.calculator_started = True
                contestant.contestanttrack.save(update_fields=["calculator_started"])
            return contestant

        self.never_started = make_contestant(1, calculator_started=False)
        self.finished = make_contestant(2, calculator_started=True)
        self.currently_running = make_contestant(3, calculator_started=True)
        self.dispatch_pending = make_contestant(4, calculator_started=True)

        calculator_is_alive(self.currently_running.pk, 30)
        calculator_dispatch_pending(self.dispatch_pending.pk, 30)

    def test_only_currently_running_contestants_are_excluded(self, *args):
        form = BatchContestantUpdateForm(navigation_task=self.navigation_task)
        choice_pks = {pk for pk, _ in form.fields["contestant_ids"].choices}

        self.assertIn(str(self.never_started.pk), choice_pks)
        # calculator_started=True but not currently running - must remain editable (this is the bug).
        self.assertIn(str(self.finished.pk), choice_pks)
        self.assertNotIn(str(self.currently_running.pk), choice_pks)
        self.assertNotIn(str(self.dispatch_pending.pk), choice_pks)
