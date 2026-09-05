"""
Regression tests for the CIMA "start at a maximum, subtract penalties" scoring model
(descending scorecards), covering the two pieces added to make it actually work:

1. NavigationTask.assign_scorecard_from_original applies a per-subtype scoring baseline
   (score_sorting_direction/initial_score) to a freshly-copied task scorecard, without ever
   touching the shared "original" scorecard templates legacy tasks also use.
2. ContestantProcessor.update_score_from_thread negates the penalty magnitude for a descending
   scorecard, so it is subtracted from initial_score instead of added to it - the design intent
   documented in documentation/cima/CIMA_Task_catalogue_implementation_plan.md ("applying
   negative penalties") which was never wired up before this.

update_score_from_thread is exercised directly against a bare (object.__new__) ContestantProcessor
rather than a fully constructed one, deliberately - __init__ pulls in Redis/Traccar/thread setup
that has nothing to do with the scoring-sign logic under test here; see
test_contestant_processor_auto_terminate.py for a test exercising the fully constructed processor.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from display.calculators.cima_score_normalization import get_cima_gate_qmax
from display.calculators.contestant_processor import ContestantProcessor, ScoreAccumulator
from display.calculators.gate_calculator import GATE_SCORE_TYPE
from display.calculators.update_score_message import UpdateScoreMessage
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    ANOMALY,
    Aeroplane,
    Contest,
    Contestant,
    ContestantTaskConfiguration,
    Crew,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
)
from display.utilities.cima_task_type_definitions import (
    ANR_CATALOGUE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TURNPOINT_HUNT,
)
from display.utilities.gate_definitions import TURNPOINT
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCimaDescendingScoring(TestCase):
    def setUp(self, *args):
        create_scorecards()
        self.precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.anr_original = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        self.contest = Contest.objects.create(
            name="CIMA descending scoring test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Cima", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-CIMA"))

    def _make_task(self, original_scorecard, task_subtype=None) -> NavigationTask:
        return NavigationTask.create(
            name=f"task-{task_subtype}",
            contest=self.contest,
            route=Route.objects.create(name=f"route-{task_subtype}"),
            original_scorecard=original_scorecard,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=task_subtype,
        )

    def _make_contestant(self, navigation_task: NavigationTask) -> Contestant:
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"cima-{navigation_task.pk}",
            contestant_number=1,
        )

    def _bare_processor(self, contestant: Contestant) -> ContestantProcessor:
        # Bypasses __init__ deliberately - see module docstring.
        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = True
        processor.score = processor.scorecard.initial_score
        return processor

    @staticmethod
    def _penalty_message(points: float) -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name="TP1"),
            score=points,
            message="test penalty",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type="test_penalty",
        )

    def test_cima_precision_subtype_gets_descending_scorecard_with_max_of_1000(self, *args):
        task = self._make_task(self.precision_original, task_subtype=PRECISION_NAVIGATION)
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 1000)
        # The shared original template must be untouched - legacy tasks copy the same original.
        self.precision_original.refresh_from_db()
        self.assertEqual(self.precision_original.score_sorting_direction, "asc")
        self.assertEqual(self.precision_original.initial_score, 0)

    def test_cima_anr_catalogue_subtype_gets_descending_scorecard_with_max_of_1000(self, *args):
        # 1000, not 2000: the catalogue's own Q formula starts at 2000, but its final
        # P = 1000 * Q / Qmax step (Qmax fixed at 2000 for ANR) halves everything - initial_score
        # is 1000 here so self.score always reflects P directly. See
        # get_cima_fixed_scale_factor/CIMA_FIXED_SCALE_FACTORS.
        task = self._make_task(self.anr_original, task_subtype=ANR_CATALOGUE)
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 1000)

    def test_legacy_task_scorecard_is_unaffected(self, *args):
        task = self._make_task(self.precision_original, task_subtype=None)
        self.assertEqual(task.scorecard.score_sorting_direction, "asc")
        self.assertEqual(task.scorecard.initial_score, 0)

    def test_descending_scorecard_subtracts_penalty_from_initial_score(self, *args):
        task = self._make_task(self.precision_original, task_subtype=PRECISION_NAVIGATION)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 1000)

        processor.update_score_from_thread(self._penalty_message(30))
        self.assertEqual(processor.score, 970)

        processor.update_score_from_thread(self._penalty_message(15.5))
        self.assertEqual(processor.score, 954.5)

    def test_ascending_scorecard_still_adds_penalty_as_before(self, *args):
        # Same penalty magnitudes as the descending test above, against an unmodified legacy
        # scorecard - confirms the sign change is genuinely conditional, not a global flip.
        task = self._make_task(self.precision_original, task_subtype=None)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        processor.update_score_from_thread(self._penalty_message(30))
        self.assertEqual(processor.score, 30)

        processor.update_score_from_thread(self._penalty_message(15.5))
        self.assertEqual(processor.score, 45.5)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestCimaGateQmaxNormalization(TestCase):
    """
    Covers the Qmax normalization piece added on top of TestCimaDescendingScoring's flat
    "subtract raw penalty" model: for GATE_SCORE_TYPE events on a subtype get_cima_gate_qmax
    supports (PRECISION_NAVIGATION here), the score must move proportionally
    (initial_score * (1 - cumulative_gate_deficit / qmax)), not by the raw penalty magnitude -
    see cima_score_normalization.py for why. Non-gate score types (e.g. backtracking) must keep
    the old flat-subtraction behavior untouched - TestCimaDescendingScoring already covers that
    with score_type="test_penalty"; kept out of scope here to avoid duplicating it.
    """

    def setUp(self, *args):
        create_scorecards()
        Scorecard.SCORECARD_CACHE.clear()
        self.precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="CIMA Qmax test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Qmax", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-QMAX"))

    def tearDown(self, *args):
        Scorecard.SCORECARD_CACHE.clear()

    @staticmethod
    def _turnpoint(name: str) -> Waypoint:
        waypoint = Waypoint(name)
        waypoint.type = TURNPOINT
        # gate_check/time_check must be explicitly set - a Waypoint defaults both to False (see
        # waypoint.py), and get_cima_gate_qmax only counts a gate's worst-case penalty toward
        # Qmax if at least one of these is set, matching what could actually be scored for it.
        waypoint.gate_check = True
        waypoint.time_check = True
        return waypoint

    def _make_two_turnpoint_task(self) -> NavigationTask:
        route = Route.objects.create(name="qmax-route", waypoints=[self._turnpoint("TP1"), self._turnpoint("TP2")])
        task = NavigationTask.create(
            name="qmax-task",
            contest=self.contest,
            route=route,
            original_scorecard=self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=PRECISION_NAVIGATION,
        )
        # tp worst-case = max(missed_penalty, maximum_penalty) = max(200, 150) = 200 per gate,
        # so qmax = 2 * 200 = 400 for this two-turnpoint route.
        task.scorecard.config.setdefault("gates", {})[TURNPOINT] = {"missed_penalty": 200, "maximum_penalty": 150}
        task.scorecard.save(update_fields=["config"])
        return task

    def _make_contestant(self, navigation_task: NavigationTask) -> Contestant:
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"qmax-{navigation_task.pk}",
            contestant_number=1,
        )

    def _bare_processor(self, contestant: Contestant) -> ContestantProcessor:
        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = True
        processor.score = processor.scorecard.initial_score
        return processor

    @staticmethod
    def _gate_penalty_message(gate_name: str, points: float) -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name=gate_name),
            score=points,
            message="test gate penalty",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type=GATE_SCORE_TYPE,
        )

    def test_gate_penalties_are_normalized_proportionally_to_qmax_not_subtracted_flat(self, *args):
        task = self._make_two_turnpoint_task()
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 1000)

        # Cumulative gate deficit 50 of qmax 400 -> 1000 * (1 - 50/400) = 875, NOT 1000 - 50 = 950.
        processor.update_score_from_thread(self._gate_penalty_message("TP1", 50))
        self.assertEqual(processor.score, 875)

        # Cumulative gate deficit 200 of qmax 400 -> 1000 * (1 - 200/400) = 500.
        processor.update_score_from_thread(self._gate_penalty_message("TP2", 150))
        self.assertEqual(processor.score, 500)

    def test_non_cima_subtype_falls_back_to_flat_subtraction_for_gate_events_too(self, *args):
        # Same route/scorecard shape, but a legacy (non-normalized) subtype: get_cima_gate_qmax
        # returns None, so GATE_SCORE_TYPE events must fall back to the original flat behavior.
        route = Route.objects.create(name="legacy-route", waypoints=[self._turnpoint("TP1")])
        task = NavigationTask.create(
            name="legacy-task",
            contest=self.contest,
            route=route,
            original_scorecard=self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=None,
        )
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        processor.update_score_from_thread(self._gate_penalty_message("TP1", 30))
        self.assertEqual(processor.score, 30)

    def test_falls_back_to_flat_addition_when_scorecard_reconfigured_to_ascending(self, *args):
        # Regression test (CodeRabbit finding on #756): score_sorting_direction and
        # initial_score are freely organizer-editable independent of task_subtype (the
        # scorecard editor's General group) - get_cima_gate_qmax only checks
        # effective_task_subtype, so it still returns a qmax here even though the scorecard was
        # edited back to ascending after creation. Without the direction guard,
        # _cima_normalized_gate_score_delta would apply the "start at ceiling, subtract" formula
        # to a scorecard that isn't one, producing a nonsensical negative-going result instead
        # of the correct ascending-accumulate-from-0 behavior.
        task = self._make_two_turnpoint_task()
        task.scorecard.score_sorting_direction = "asc"
        task.scorecard.initial_score = 0
        task.scorecard.save(update_fields=["score_sorting_direction", "initial_score"])
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        processor.update_score_from_thread(self._gate_penalty_message("TP1", 50))
        self.assertEqual(processor.score, 50)  # raw magnitude, added - not desc-normalized

    def test_falls_back_to_flat_subtraction_when_initial_score_is_cleared_to_zero(self, *args):
        # Same organizer-editability concern, the other failure mode: initial_score=0 with
        # score_sorting_direction still "desc" would make new_component = 0 * (...) always 0,
        # silently erasing all scoring signal regardless of actual performance, if
        # _cima_normalized_gate_score_delta didn't guard against it.
        task = self._make_two_turnpoint_task()
        task.scorecard.initial_score = 0
        task.scorecard.save(update_fields=["initial_score"])
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        processor.update_score_from_thread(self._gate_penalty_message("TP1", 50))
        self.assertEqual(processor.score, -50)  # raw magnitude, sign-flipped and subtracted from 0

    def test_qmax_uses_contestant_declared_subset_not_the_full_shared_route(self, *args):
        # 2.A3 (CONTRACT_NAVIGATION_TIME_CONTROLS): the organizer's shared route can carry many
        # more catalogue turnpoints than any one contestant declares to fly - see
        # cima_score_normalization.py's docstring on why Qmax must read the contestant's
        # EFFECTIVE route (via get_effective_route_waypoints), not navigation_task.route.
        # Three shared-route turnpoints, but this contestant only declared one of them.
        route = Route.objects.create(
            name="contract-route",
            waypoints=[self._turnpoint("TP1"), self._turnpoint("TP2"), self._turnpoint("TP3")],
        )
        task = NavigationTask.create(
            name="contract-task",
            contest=self.contest,
            route=route,
            original_scorecard=self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
        )
        task.scorecard.config.setdefault("gates", {})[TURNPOINT] = {"missed_penalty": 200, "maximum_penalty": 150}
        task.scorecard.save(update_fields=["config"])
        contestant = self._make_contestant(task)
        ContestantTaskConfiguration.objects.create(
            contestant=contestant,
            task_subtype=CONTRACT_NAVIGATION_TIME_CONTROLS,
            is_valid=True,
            compiled_effective_route_payload={
                "effective_waypoints": [
                    {
                        "name": "TP1",
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "type": TURNPOINT,
                        "width": 0.1,
                        "time_check": True,
                        "gate_check": True,
                    }
                ]
            },
        )

        # Only TP1 was declared -> qmax = 200, not 3 * 200 = 600 for the full shared route.
        self.assertEqual(get_cima_gate_qmax(contestant), 200)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestTurnpointHuntAchievementSignHandling(TestCase):
    """
    2.A6/2.B2 are the only CIMA subtypes using an ADDITIVE-from-zero model rather than "start at
    a ceiling, subtract" (see cima_task_type_definitions.CIMA_SCORING_BASELINE's docstring) -
    their achievement score_types (turnpoint_hunt_target_value, turnpoint_hunt_sequence_bonus)
    must be added as-is under score_sorting_direction=desc, NOT sign-flipped like every other
    desc score_type. Without ACHIEVEMENT_SCORE_TYPES, more achievement would produce a LOWER
    total (since the flip would subtract it from 0), ranking a contestant who identifies more
    targets WORSE - the opposite of the catalogue's intent.
    """

    def setUp(self, *args):
        create_scorecards()
        self.precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Turnpoint hunt sign test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Achievement", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ACHV"))

    def _make_task(self, task_subtype) -> NavigationTask:
        return NavigationTask.create(
            name=f"achievement-task-{task_subtype}",
            contest=self.contest,
            route=Route.objects.create(name=f"achievement-route-{task_subtype}"),
            original_scorecard=self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=task_subtype,
        )

    def _make_contestant(self, navigation_task: NavigationTask) -> Contestant:
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"achievement-{navigation_task.pk}",
            contestant_number=1,
        )

    def _bare_processor(self, contestant: Contestant) -> ContestantProcessor:
        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = True
        processor.score = processor.scorecard.initial_score
        return processor

    @staticmethod
    def _message(score_type: str, points: float) -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name="A"),
            score=points,
            message="test",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type=score_type,
        )

    def test_turnpoint_hunt_subtype_gets_additive_desc_zero_baseline(self, *args):
        task = self._make_task(TURNPOINT_HUNT)
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 0)

    def test_limited_fuel_turnpoint_hunt_subtype_gets_additive_desc_zero_baseline(self, *args):
        task = self._make_task(LIMITED_FUEL_TURNPOINT_HUNT)
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 0)

    def test_target_value_achievement_is_added_not_subtracted(self, *args):
        task = self._make_task(TURNPOINT_HUNT)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 100))
        self.assertEqual(processor.score, 100)  # NOT -100

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 200))
        self.assertEqual(processor.score, 300)  # NOT -300

    def test_sequence_bonus_achievement_is_added_not_subtracted(self, *args):
        task = self._make_task(TURNPOINT_HUNT)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("turnpoint_hunt_sequence_bonus", 50))
        self.assertEqual(processor.score, 50)  # NOT -50

    def test_genuine_penalty_score_types_still_subtract_under_desc(self, *args):
        # gate_score (a genuine penalty for turnpoint hunt too - a missed photo/gate) and the
        # other turnpoint-hunt penalty types must NOT be exempted - only the two achievement
        # types in ACHIEVEMENT_SCORE_TYPES are.
        task = self._make_task(TURNPOINT_HUNT)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("gate_score", 30))
        self.assertEqual(processor.score, -30)

        processor.update_score_from_thread(self._message("turnpoint_hunt_compulsory_timing", 20))
        self.assertEqual(processor.score, -50)

    def test_mixed_achievement_and_penalty_nets_correctly(self, *args):
        task = self._make_task(TURNPOINT_HUNT)
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 100))
        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 200))
        processor.update_score_from_thread(self._message("turnpoint_hunt_compulsory_timing", 25))
        processor.update_score_from_thread(self._message("turnpoint_hunt_sequence_bonus", 50))
        # 100 + 200 - 25 + 50 = 325
        self.assertEqual(processor.score, 325)


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestAnrFixedScaleFactor(TestCase):
    """
    2.A8's catalogue formula is "Q = 2000 - Pnav - Ptime - Pfpr - Pto - Prr - Pbc,
    P = 1000 * Q / Qmax" with Qmax fixed at 2000 - a uniform half-scale applied to every one of
    ANR's penalty terms (including backtracking/circling, which - unlike 2.A1-2.A5 - the
    catalogue counts INSIDE this formula, not as a separate flat deduction). initial_score=1000
    (not 2000) plus get_cima_fixed_scale_factor halving every score message reproduces this
    exactly.
    """

    def setUp(self, *args):
        create_scorecards()
        self.anr_original = Scorecard.get_originals().get(shortcut_name="FAI ANR")
        self.contest = Contest.objects.create(
            name="ANR fixed scale test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Anr", last_name="Pilot"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ANRF"))

    def _make_task(self) -> NavigationTask:
        return NavigationTask.create(
            name="anr-fixed-scale-task",
            contest=self.contest,
            route=Route.objects.create(name="anr-fixed-scale-route"),
            original_scorecard=self.anr_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=ANR_CATALOGUE,
        )

    def _make_contestant(self, navigation_task: NavigationTask) -> Contestant:
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        return Contestant.objects.create(
            navigation_task=navigation_task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"anr-fixed-scale-{navigation_task.pk}",
            contestant_number=1,
        )

    def _bare_processor(self, contestant: Contestant) -> ContestantProcessor:
        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = True
        processor.score = processor.scorecard.initial_score
        return processor

    @staticmethod
    def _message(score_type: str, points: float) -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name="SP"),
            score=points,
            message="test",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type=score_type,
        )

    def test_anr_starts_at_1000_not_2000(self, *args):
        task = self._make_task()
        self.assertEqual(task.scorecard.score_sorting_direction, "desc")
        self.assertEqual(task.scorecard.initial_score, 1000)

    def test_corridor_deviation_penalty_is_halved(self, *args):
        task = self._make_task()
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 1000)

        processor.update_score_from_thread(self._message("gate_score", 40))
        self.assertEqual(processor.score, 980)  # 1000 - 40/2, NOT 1000 - 40

    def test_backtracking_penalty_is_also_halved(self, *args):
        # Unlike 2.A1-2.A5 (where backtracking is a separate flat deduction, excluded from
        # Qmax), 2.A8's own Q formula sums Pbc together with every other term - so it must get
        # the same uniform scale, not the untouched-linear treatment backtracking gets elsewhere.
        task = self._make_task()
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("backtracking", 200))
        self.assertEqual(processor.score, 900)  # 1000 - 200/2, NOT 1000 - 200

    def test_mixed_anr_penalties_all_scaled_consistently(self, *args):
        task = self._make_task()
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("gate_score", 40))
        processor.update_score_from_thread(self._message("anr_route_to_sp", 200))
        processor.update_score_from_thread(self._message("anr_takeoff_timing", 100))
        processor.update_score_from_thread(self._message("backtracking", 200))
        # 1000 - (40 + 200 + 100 + 200) / 2 = 1000 - 270 = 730
        self.assertEqual(processor.score, 730)

    def test_non_anr_desc_subtype_is_not_scaled(self, *args):
        # get_cima_fixed_scale_factor must be scoped to ANR_CATALOGUE only - a 2.A1-2.A5 task
        # (no route, so get_cima_gate_qmax returns None and this falls back to raw magnitude)
        # must not also get halved.
        precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        task = NavigationTask.create(
            name="precision-not-scaled-task",
            contest=self.contest,
            route=Route.objects.create(name="precision-not-scaled-route"),
            original_scorecard=precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=PRECISION_NAVIGATION,
        )
        contestant = self._make_contestant(task)
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 1000)

        processor.update_score_from_thread(self._message("test_penalty", 40))
        self.assertEqual(processor.score, 960)  # 1000 - 40, not halved


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestTurnpointHuntAchievementQmaxNormalization(TestCase):
    """
    2.A6/2.B2's final P = 1000 * Q / Qmax normalization, applied to the achievement component
    only (turnpoint_hunt_target_value + turnpoint_hunt_sequence_bonus combined) - see
    get_cima_achievement_qmax. Penalty score_types (gate_score, compulsory timing, ...) keep
    accumulating linearly, untouched, exactly like TestCimaGateQmaxNormalization from earlier in
    this file for 2.A1-2.A5's non-gate penalties.
    """

    def setUp(self, *args):
        create_scorecards()
        Scorecard.SCORECARD_CACHE.clear()
        self.precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Turnpoint hunt achievement qmax test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Achv", last_name="Qmax"))
        self.team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ACHVQ"))

    def tearDown(self, *args):
        Scorecard.SCORECARD_CACHE.clear()

    def _make_task_and_contestant_with_targets(self, target_values: dict, sequence_bonus: float = 0):
        task = NavigationTask.create(
            name="achv-qmax-task",
            contest=self.contest,
            route=Route.objects.create(name="achv-qmax-route"),
            original_scorecard=self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=TURNPOINT_HUNT,
        )
        if sequence_bonus:
            task.scorecard.config["turnpoint_hunt_sequence_bonus"] = sequence_bonus
            task.scorecard.save(update_fields=["config"])
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        contestant = Contestant.objects.create(
            navigation_task=task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"achv-qmax-{task.pk}",
            contestant_number=1,
        )
        ContestantTaskConfiguration.objects.create(
            contestant=contestant,
            task_subtype=TURNPOINT_HUNT,
            is_valid=True,
            compiled_effective_route_payload={"scored_target_values": target_values},
        )
        return contestant

    def _bare_processor(self, contestant: Contestant) -> ContestantProcessor:
        processor = object.__new__(ContestantProcessor)
        processor.contestant = contestant
        processor.scorecard = contestant.navigation_task.scorecard
        processor.accumulated_scores = ScoreAccumulator()
        processor.gate_scores = {}
        processor.suppress_side_effects = True
        processor.score = processor.scorecard.initial_score
        return processor

    @staticmethod
    def _message(score_type: str, points: float, gate_name: str = "A") -> UpdateScoreMessage:
        return UpdateScoreMessage(
            time=datetime.datetime(2026, 1, 1, 8, 5, tzinfo=datetime.timezone.utc),
            gate=SimpleNamespace(name=gate_name),
            score=points,
            message="test",
            latitude=60.0,
            longitude=11.0,
            annotation_type=ANOMALY,
            score_type=score_type,
        )

    def test_achievement_normalized_against_declared_target_value_ceiling(self, *args):
        # Two declared targets worth 100 total (60 + 40) -> qmax = 100.
        contestant = self._make_task_and_contestant_with_targets({"A": 60, "B": 40})
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 0)

        # Achieved 60 of 100 -> 1000 * 60/100 = 600, NOT the raw 60.
        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 60, "A"))
        self.assertEqual(processor.score, 600)

        # Achieved 100 of 100 -> full 1000.
        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 40, "B"))
        self.assertEqual(processor.score, 1000)

    def test_sequence_bonus_included_in_achievement_qmax_and_component(self, *args):
        # One target worth 80, plus a 20-point sequence bonus -> qmax = 100.
        contestant = self._make_task_and_contestant_with_targets({"A": 80}, sequence_bonus=20)
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 80, "A"))
        self.assertEqual(processor.score, 800)  # 1000 * 80/100

        processor.update_score_from_thread(self._message("turnpoint_hunt_sequence_bonus", 20, "A"))
        self.assertEqual(processor.score, 1000)  # 1000 * 100/100

    def test_penalty_score_types_still_accumulate_linearly_alongside_normalized_achievement(self, *args):
        contestant = self._make_task_and_contestant_with_targets({"A": 100})
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 50, "A"))
        self.assertEqual(processor.score, 500)  # 1000 * 50/100

        processor.update_score_from_thread(self._message("turnpoint_hunt_compulsory_timing", 30, "CP1"))
        self.assertEqual(processor.score, 470)  # 500 - 30, penalty untouched by normalization

    def test_no_valid_declaration_falls_back_to_raw_achievement_sum(self, *args):
        task = NavigationTask.create(
            name="achv-no-config-task",
            contest=self.contest,
            route=Route.objects.create(name="achv-no-config-route"),
            original_scorecard=self.precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
            task_subtype=TURNPOINT_HUNT,
        )
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        contestant = Contestant.objects.create(
            navigation_task=task,
            team=self.team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id=f"achv-no-config-{task.pk}",
            contestant_number=1,
        )
        # No ContestantTaskConfiguration at all - get_cima_achievement_qmax returns None.
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 42, "A"))
        self.assertEqual(processor.score, 42)  # raw, un-normalized

    def test_falls_back_to_raw_sum_when_scorecard_reconfigured_to_ascending(self, *args):
        # Same organizer-editability concern as TestCimaGateQmaxNormalization's analogous test:
        # score_sorting_direction is freely editable independent of task_subtype, so
        # get_cima_achievement_qmax still returns a qmax here even after the scorecard was
        # edited away from the desc/climb-from-0 model this normalization assumes.
        contestant = self._make_task_and_contestant_with_targets({"A": 60, "B": 40})
        contestant.navigation_task.scorecard.score_sorting_direction = "asc"
        contestant.navigation_task.scorecard.save(update_fields=["score_sorting_direction"])
        processor = self._bare_processor(contestant)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 60, "A"))
        self.assertEqual(processor.score, 60)  # raw magnitude, not normalized to 1000*60/100

    def test_falls_back_to_raw_sum_when_scorecard_has_a_non_zero_initial_score(self, *args):
        # Regression test (CodeRabbit follow-up finding on #756): score_sorting_direction alone
        # isn't enough to guard this - self._cima_achievement_component always starts at 0 (see
        # _get_cima_achievement_qmax), but self.score starts at scorecard.initial_score. If an
        # organizer keeps "desc" and sets initial_score to 100, a full achievement would apply a
        # delta of 1000 on top of that starting 100, landing on 1100 instead of the intended
        # fixed 1000 ceiling - the two trackers silently drift apart.
        contestant = self._make_task_and_contestant_with_targets({"A": 100})
        contestant.navigation_task.scorecard.initial_score = 100
        contestant.navigation_task.scorecard.save(update_fields=["initial_score"])
        processor = self._bare_processor(contestant)
        self.assertEqual(processor.score, 100)

        processor.update_score_from_thread(self._message("turnpoint_hunt_target_value", 100, "A"))
        self.assertEqual(processor.score, 200)  # 100 + raw 100, NOT 100 + 1000*100/100 = 1100
