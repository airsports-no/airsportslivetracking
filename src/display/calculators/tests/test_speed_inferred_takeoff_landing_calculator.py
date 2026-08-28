import datetime
from unittest.mock import MagicMock

from django.test import TestCase

from display.calculators.calculator import LandingPassedEvent, OrchestratorState, TakeoffPassedEvent
from display.calculators.speed_inferred_takeoff_landing_calculator import (
    NEAR_ZERO_SPEED_THRESHOLD_KT,
    SUSTAINED_SAMPLE_COUNT,
    SpeedInferredTakeoffLandingCalculator,
)
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector


class TestSpeedInferredTakeoffLandingCalculator(TestCase):
    def setUp(self):
        self.contestant = MagicMock()
        self.contestant.navigation_task.task_subtype = "duration"

        self.scorecard = MagicMock()
        self.scorecard.get_extended_gate_width_for_gate_type.return_value = 200.0

        self.route = MagicMock()
        self.route.takeoff_gates = []
        self.route.landing_gates = []

        self.queue = MagicMock()
        self.projector = Projector(60, 11)
        self.base_time = datetime.datetime(2026, 1, 1, 10, 0, tzinfo=datetime.timezone.utc)

        self.calculator = SpeedInferredTakeoffLandingCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.queue,
            live_processing=False,
            projector=self.projector,
        )

        self.state = OrchestratorState(
            last_gate=None,
            last_visible_gate=None,
            next_gate=None,
            in_range_of_gate=None,
            projector=self.projector,
            has_passed_finishpoint=False,
            recalculation_completed=True,
        )

    def _position(self, index: int, speed: float) -> ContestantReceivedPosition:
        pos = MagicMock(spec=ContestantReceivedPosition)
        pos.latitude = 60.0
        pos.longitude = 11.0 + index * 0.0001
        pos.time = self.base_time + datetime.timedelta(seconds=index)
        pos.speed = speed
        return pos

    def _feed(self, track, index, speed):
        position = self._position(index, speed)
        track.append(position)
        return self.calculator.calculate_enroute(track, self.state)

    def test_infers_takeoff_after_sustained_low_speed_hold(self):
        track = []
        events = []
        for i in range(SUSTAINED_SAMPLE_COUNT):
            events = self._feed(track, i, 0)
        self.assertEqual(events, [])
        self.assertFalse(self.calculator.airborne)

        # First sample above threshold right after the sustained hold.
        events = self._feed(track, SUSTAINED_SAMPLE_COUNT, NEAR_ZERO_SPEED_THRESHOLD_KT + 50)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], TakeoffPassedEvent)
        self.assertTrue(self.calculator.airborne)
        self.assertTrue(self.calculator.scored_takeoff)
        self.assertEqual(events[0].gate.type, "to")

        # It should not fire again on subsequent fast samples.
        events = self._feed(track, SUSTAINED_SAMPLE_COUNT + 1, 80)
        self.assertEqual(events, [])

    def test_infers_landing_only_once_low_speed_is_sustained(self):
        track = []
        index = 0
        # Get airborne first.
        for _ in range(SUSTAINED_SAMPLE_COUNT):
            self._feed(track, index, 0)
            index += 1
        takeoff_events = self._feed(track, index, 80)
        index += 1
        self.assertEqual(len(takeoff_events), 1)

        # Cruise for a while.
        for _ in range(SUSTAINED_SAMPLE_COUNT):
            events = self._feed(track, index, 80)
            index += 1
            self.assertEqual(events, [])

        # Drop below threshold - should not fire until sustained for the full window.
        for _ in range(SUSTAINED_SAMPLE_COUNT - 1):
            events = self._feed(track, index, 0)
            index += 1
            self.assertEqual(events, [])

        # The sample that completes the sustained low-speed window triggers landing.
        events = self._feed(track, index, 0)
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], LandingPassedEvent)
        self.assertTrue(self.calculator.scored_landing)
        self.assertEqual(events[0].gate.type, "ldg")

    def test_stays_silent_when_gates_are_authored(self):
        self.route.takeoff_gates = [MagicMock()]
        self.route.landing_gates = [MagicMock()]
        calculator = SpeedInferredTakeoffLandingCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.queue,
            live_processing=False,
            projector=self.projector,
        )
        self.assertFalse(calculator.infer_takeoff)
        self.assertFalse(calculator.infer_landing)

        track = []
        events = []
        for i in range(SUSTAINED_SAMPLE_COUNT + 5):
            position = self._position(i, 0)
            track.append(position)
            events.extend(calculator.calculate_enroute(track, self.state))
        for i in range(SUSTAINED_SAMPLE_COUNT, SUSTAINED_SAMPLE_COUNT + 5):
            position = self._position(SUSTAINED_SAMPLE_COUNT + 5 + i, 80)
            track.append(position)
            events.extend(calculator.calculate_enroute(track, self.state))
        self.assertEqual(events, [])

    def test_tracks_airborne_state_from_real_takeoff_event_when_only_landing_is_inferred(self):
        self.route.takeoff_gates = [MagicMock()]
        self.route.landing_gates = []
        calculator = SpeedInferredTakeoffLandingCalculator(
            self.contestant,
            self.scorecard,
            self.route,
            self.queue,
            live_processing=False,
            projector=self.projector,
        )
        self.assertFalse(calculator.infer_takeoff)
        self.assertTrue(calculator.infer_landing)

        # Simulate the real TakeoffAndLandingGateCalculator emitting the actual event.
        real_gate = MagicMock()
        takeoff_position = self._position(0, 80)
        calculator.on_takeoff_passed(TakeoffPassedEvent(real_gate, takeoff_position, takeoff_position.time))
        self.assertTrue(calculator.airborne)

        track = [takeoff_position]
        index = 1
        for _ in range(SUSTAINED_SAMPLE_COUNT):
            events = self._feed(track, index, 80)
            index += 1
            self.assertEqual(events, [])
        events = []
        for _ in range(SUSTAINED_SAMPLE_COUNT):
            position = self._position(index, 0)
            track.append(position)
            events = calculator.calculate_enroute(track, self.state)
            index += 1
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], LandingPassedEvent)
