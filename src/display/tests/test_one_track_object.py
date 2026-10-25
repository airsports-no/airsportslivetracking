"""
The live calculators work with one ContestantTrack object per contestant. contestant.refresh_from_db() replaces the
cached track, and the calculators then had two or three copies of it, each only knowing what it changed itself, which
let a push tell the browser a contestant that had crossed the start line was not started. refresh_contestant_in_place
refreshes the contestant and keeps the track.
"""

import datetime
import re
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from display.calculators.calculator_utilities import refresh_contestant_in_place
from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Aeroplane, Contest, Contestant, ContestantTrack, Crew, NavigationTask, Person, Route, Team
from utilities.mock_utilities import TraccarMock

CALCULATORS = Path(__file__).resolve().parent.parent / "calculators"


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestRefreshKeepsTheTrack(TestCase):
    def make_contestant(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        contest = Contest.objects.create(
            name="One track", start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
        )
        task = NavigationTask.create(
            name="One track task",
            original_scorecard=get_default_scorecard(),
            route=Route.objects.create(name="One track route"),
            contest=contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="P", last_name="One", email="p@one.example"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ONE"))
        return Contestant.objects.create(
            team=team,
            navigation_task=task,
            takeoff_time=now + datetime.timedelta(hours=1),
            finished_by_time=now + datetime.timedelta(hours=2),
            tracker_start_time=now + datetime.timedelta(minutes=30),
            tracker_device_id="one-track-device",
            contestant_number=1,
            air_speed=70,
        )

    def test_a_plain_refresh_replaces_the_track(self, *args):
        # The behaviour the helper is there for: if Django stops doing this, the helper is not needed.
        contestant = self.make_contestant()
        track = contestant.contestanttrack
        contestant.refresh_from_db()
        self.assertIsNot(contestant.contestanttrack, track)

    def test_the_helper_reloads_the_contestant_and_keeps_the_one_track(self, *args):
        contestant = self.make_contestant()
        track = contestant.contestanttrack
        Contestant.objects.filter(pk=contestant.pk).update(air_speed=95)
        ContestantTrack.objects.filter(pk=track.pk).update(passed_starting_gate=True, current_state="Started")

        refresh_contestant_in_place(contestant)

        self.assertEqual(contestant.air_speed, 95)  # the contestant's own fields are up to date
        self.assertIs(contestant.contestanttrack, track)  # and it is still the one track object
        track.refresh_from_db()  # refreshed in place, as the processor does it
        self.assertTrue(contestant.contestanttrack.passed_starting_gate)
        self.assertEqual(contestant.contestanttrack.current_state, "Started")


class TestTheLivePathKeepsToTheRules(SimpleTestCase):
    """Cheap guards on the source: the two ways the copies came back."""

    def source(self, name):
        return (CALCULATORS / name).read_text()

    def test_the_processor_refreshes_its_contestant_without_replacing_the_track(self):
        self.assertIsNone(
            re.search(r"self\.contestant\.refresh_from_db\(\)", self.source("contestant_processor.py")),
            "use refresh_contestant_in_place(self.contestant): a plain refresh replaces the contestant's track object",
        )

    def test_no_calculator_saves_a_whole_track(self):
        # A copy that is behind would write its old values over the columns the others have changed.
        for path in CALCULATORS.glob("*.py"):
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(r"(contestanttrack|contestant_track)\.save\(\s*\)", line):
                    self.fail(f"{path.name}:{number} saves a whole ContestantTrack; save only the fields changed (update_fields)")
