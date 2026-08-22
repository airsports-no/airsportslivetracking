import datetime
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.calculators.calculator import LandingPassedEvent, TakeoffPassedEvent
from display.calculators.calculator_factory import calculator_factory
from display.calculators.duration_calculator import DurationCalculator
from display.calculators.update_score_message import UpdateScoreMessage
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import Aeroplane, Contest, Contestant, Crew, EditableRoute, NavigationTask, Person, Scorecard, Team
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.cima_task_type_definitions import DURATION
from display.utilities.coordinate_utilities import Projector
from display.utilities.navigation_task_type_definitions import PRECISION
from utilities.mock_utilities import TraccarMock


class TestDurationCalculator(TestCase):
    def setUp(self):
        self.projector = Projector(60, 11)
        self.queue = MagicMock()
        self.contestant = MagicMock()
        self.contestant.navigation_task.task_subtype = DURATION
        self.contestant.navigation_task.editable_route = None
        # No compiled ContestantTaskConfiguration / Route-level Prohibited zone
        # in this mock-driven suite - explicit None/empty so
        # DurationCalculator's snapshot/route fallbacks correctly cascade down
        # to whatever editable_route a test configures, instead of treating an
        # unspecced MagicMock attribute as real (truthy) landing-area data.
        self.contestant.contestanttaskconfiguration = None
        self.scorecard = MagicMock()
        self.scorecard.prohibited_zone_penalty = 200
        self.scorecard.duration_normalization_policy = ""
        self.route = MagicMock()
        self.route.landing_gates = []
        self.route.prohibited_set.filter.return_value.first.return_value = None
        self.calculator = self._build_calculator()

    def _build_calculator(self):
        return DurationCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.queue,
            live_processing=False,
            projector=self.projector,
        )

    def _make_gate(self, name):
        gate = MagicMock()
        gate.name = name
        gate.type = "tp"
        gate.expected_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        return gate

    def _make_position(self, when):
        position = MagicMock()
        position.time = when
        position.latitude = 60.0
        position.longitude = 11.0
        return position

    def _make_polygon(self, west=10.9, south=59.9, east=11.1, north=60.1):
        return [(west, south), (east, south), (east, north), (west, north)]

    def test_duration_calculator_records_airborne_duration_on_landing(self):
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 7, 30, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.queue.put_nowait.assert_called_once()
        message = self.queue.put_nowait.call_args[0][0]
        self.assertIsInstance(message, UpdateScoreMessage)
        self.assertEqual(message.score_type, "duration_airborne_time")
        self.assertEqual(message.message, "airborne duration recorded")
        self.assertEqual(message.score, 0)
        self.assertEqual(message.planned, takeoff_time)
        self.assertEqual(message.actual, landing_time)

    def test_duration_calculator_ignores_landing_without_validated_takeoff(self):
        landing_time = datetime.datetime(2026, 8, 1, 11, 7, 30, tzinfo=datetime.timezone.utc)
        landing_gate = self._make_gate("LDG")
        landing_position = self._make_position(landing_time)

        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.queue.put_nowait.assert_not_called()

    def test_duration_calculator_emits_raw_minutes_score_when_policy_configured(self):
        self.scorecard.duration_normalization_policy = "raw_minutes"
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 7, 30, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, 2)
        recorded_message = self.queue.put_nowait.call_args_list[0][0][0]
        normalized_message = self.queue.put_nowait.call_args_list[1][0][0]
        self.assertEqual(recorded_message.score_type, "duration_airborne_time")
        self.assertEqual(normalized_message.score_type, "duration_normalized_score")
        self.assertEqual(normalized_message.message, "duration normalized using raw minutes")
        self.assertEqual(normalized_message.score, 67.5)

    def test_duration_calculator_emits_landing_area_penalty_when_outside_specified_area(self):
        editable_route = MagicMock()
        editable_route.get_duration_landing_area_polygons.return_value = [
            {"geometry": {"coordinates": [self._make_polygon(west=11.2, south=60.2, east=11.4, north=60.4)]}}
        ]
        self.contestant.navigation_task.editable_route = editable_route
        # The landing-area ring is resolved once at construction time now, not
        # re-read live on every landing event - rebuild after configuring the
        # editable route this test needs.
        self.calculator = self._build_calculator()
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)
        landing_position.latitude = 60.0
        landing_position.longitude = 11.0

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, 2)
        penalty_message = self.queue.put_nowait.call_args_list[1][0][0]
        self.assertEqual(penalty_message.score_type, "duration_landing_area_outside")
        self.assertEqual(penalty_message.message, "landing outside specified area")
        self.assertEqual(penalty_message.score, 200)

    def test_duration_calculator_uses_polygon_geometry_not_bounding_box(self):
        editable_route = MagicMock()
        editable_route.get_duration_landing_area_polygons.return_value = [
            {
                "geometry": {
                    "coordinates": [[
                        (11.0, 60.0),
                        (11.2, 60.0),
                        (11.2, 60.02),
                        (11.02, 60.02),
                        (11.02, 60.2),
                        (11.0, 60.2),
                        (11.0, 60.0),
                    ]]
                }
            }
        ]
        self.contestant.navigation_task.editable_route = editable_route
        self.calculator = self._build_calculator()
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        landing_position = self._make_position(landing_time)
        landing_position.latitude = 60.10
        landing_position.longitude = 11.10

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, landing_position, landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, 2)
        penalty_message = self.queue.put_nowait.call_args_list[1][0][0]
        self.assertEqual(penalty_message.score_type, "duration_landing_area_outside")

    @patch("display.calculators.calculator_factory.Orchestrator")
    def test_calculator_factory_includes_duration_calculator_for_duration_subtype(self, orchestrator_mock):
        contestant = MagicMock()
        contestant.navigation_task.task_subtype = DURATION
        contestant.navigation_task.scorecard.calculator = PRECISION
        contestant.navigation_task.route.waypoints = [MagicMock()]
        contestant.navigation_task.route.takeoff_gates = []
        contestant.navigation_task.route.landing_gates = []
        contestant.gate_times = {}

        calculator_factory(contestant, MagicMock(), live_processing=False, projector=self.projector)

        calculators = orchestrator_mock.call_args[0][2]
        self.assertIn(DurationCalculator, calculators)

    def test_duration_calculator_takeoff_without_landing_never_scores(self):
        """CURRENT BEHAVIOR (possibly a gap, not asserted as correct): a
        contestant who takes off but never triggers a landing gate/inference
        event is never scored a duration at all. finalise() (
        duration_calculator.py:95) is a bare `return None` with no
        end-of-track fallback - unlike most other calculators, there is no
        mechanism to infer/score a duration from the last known track
        position if the landing event simply never arrives (e.g. a route
        with only a takeoff gate authored, and the speed-inferred landing
        fallback also never fires). This test documents what the code does
        today; whether finalise() should synthesize a duration from the
        last position is a design question flagged for the user, not
        something this test claims is correct."""
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        takeoff_gate = self._make_gate("T/O")
        takeoff_position = self._make_position(takeoff_time)

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.finalise([takeoff_position])

        self.queue.put_nowait.assert_not_called()

    def test_duration_calculator_second_landing_event_is_idempotent(self):
        """A second landing event after the duration has already been
        scored must not score again (the scored_duration guard,
        duration_calculator.py:20)."""
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        first_landing_time = datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc)
        second_landing_time = first_landing_time + datetime.timedelta(minutes=5)
        takeoff_gate = self._make_gate("T/O")
        landing_gate = self._make_gate("LDG")
        takeoff_position = self._make_position(takeoff_time)
        first_landing_position = self._make_position(first_landing_time)
        second_landing_position = self._make_position(second_landing_time)

        self.calculator.on_takeoff_passed(TakeoffPassedEvent(takeoff_gate, takeoff_position, takeoff_time))
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, first_landing_position, first_landing_time))
        call_count_after_first_landing = self.queue.put_nowait.call_count
        self.calculator.on_landing_passed(LandingPassedEvent(landing_gate, second_landing_position, second_landing_time))

        self.assertEqual(self.queue.put_nowait.call_count, call_count_after_first_landing)


class TestDurationCalculatorLandingAreaSource(TestCase):
    """Real DB objects (unlike TestDurationCalculator above), because these
    exercise the actual resolution priority - compiled snapshot, then the
    Route's own Prohibited row, then the live EditableRoute - which needs a
    real ContestantTaskConfiguration/Route/Prohibited chain to be meaningful.
    """

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.editable_route = EditableRoute.objects.create(
            name="Duration landing area source",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"id": "to-1", "name": "Takeoff 1", "featureType": "takeoff_gate"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.001, 60.0]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "ldg-1", "name": "Landing 1", "featureType": "landing_gate"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.1], [11.001, 60.1]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {"id": "dla-1", "name": "DLA", "featureType": "zone", "polygonType": "duration_landing_area"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[11.0, 60.0], [11.2, 60.0], [11.2, 60.2], [11.0, 60.2], [11.0, 60.0]]],
                        },
                    },
                ],
            },
        )
        self.route = self.editable_route.create_route(PRECISION, self.scorecard, None, None, task_subtype=DURATION)
        self.contest = Contest.objects.create(
            name="Duration landing area source contest",
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            time_zone="Europe/Oslo",
        )
        self.navigation_task = NavigationTask.create(
            name="Duration landing area source task",
            contest=self.contest,
            route=self.route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime.now(datetime.timezone.utc),
            finish_time=datetime.datetime.now(datetime.timezone.utc),
            task_subtype=DURATION,
        )
        self.navigation_task.editable_route = self.editable_route
        self.navigation_task.save(update_fields=["editable_route"])
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Duration", last_name="Source"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-DUR"))
        start_time = datetime.datetime(2020, 8, 1, 8, 5, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="duration-source",
            contestant_number=1,
            minutes_to_starting_point=6,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )
        ContestantTaskCompiler(self.contestant).compile(force=True)
        self.contestant.refresh_from_db()

    def _make_gate(self, name):
        gate = MagicMock()
        gate.name = name
        gate.type = "tp"
        gate.expected_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        return gate

    def _outside_landing_area_penalty(self, calculator, queue):
        takeoff_time = datetime.datetime(2026, 8, 1, 10, 0, tzinfo=datetime.timezone.utc)
        landing_time = datetime.datetime(2026, 8, 1, 11, 0, tzinfo=datetime.timezone.utc)
        takeoff_position = MagicMock(time=takeoff_time, latitude=60.0, longitude=11.0)
        landing_position = MagicMock(time=landing_time, latitude=61.0, longitude=12.0)  # well outside the polygon
        calculator.on_takeoff_passed(TakeoffPassedEvent(self._make_gate("T/O"), takeoff_position, takeoff_time))
        calculator.on_landing_passed(LandingPassedEvent(self._make_gate("LDG"), landing_position, landing_time))
        return [call.args[0] for call in queue.put_nowait.call_args_list if call.args[0].score_type == "duration_landing_area_outside"]

    def test_uses_the_compiled_snapshot_polygon_when_available(self):
        queue = MagicMock()
        calculator = DurationCalculator(self.contestant, self.scorecard, self.route, queue, live_processing=False, projector=self.navigation_task.get_projector())
        self.assertIsNotNone(calculator.landing_area_ring)
        penalties = self._outside_landing_area_penalty(calculator, queue)
        self.assertEqual(len(penalties), 1)

    def test_still_resolves_the_landing_area_when_editable_route_is_null(self):
        # Simulates EditableRoute.on_delete=SET_NULL: the compiled snapshot and
        # the Route's own Prohibited row must be enough on their own.
        self.navigation_task.editable_route = None
        self.navigation_task.save(update_fields=["editable_route"])
        self.contestant.refresh_from_db()
        queue = MagicMock()
        calculator = DurationCalculator(self.contestant, self.scorecard, self.route, queue, live_processing=False, projector=self.navigation_task.get_projector())
        self.assertIsNotNone(calculator.landing_area_ring)
        penalties = self._outside_landing_area_penalty(calculator, queue)
        self.assertEqual(len(penalties), 1)
