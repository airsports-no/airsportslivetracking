"""
Regression test for a reported bug: for an adaptive-start contestant, crossing the starting
line recalculates absolute gate times (used correctly for live scoring), but the Django
"gates and penalties" page, the live map, and API serializers kept showing the original
relative/midnight-anchored placeholder times forever afterwards.

Root cause: Contestant.gate_times (models/contestant.py) prefers
contestanttaskconfiguration.compiled_gate_times_payload over predefined_gate_times whenever a
valid ContestantTaskConfiguration exists - which is now the case for essentially every
contestant, since ContestantTaskCompiler.compile() runs for every task subtype via
contestant_persistence.create_contestant_with_related_state. compiled_gate_times_payload is
computed once, at declaration/creation time, via calculate_missing_gate_times() with no
start-time override - for an adaptive_start contestant that's the midnight-anchored relative
placeholder Contestant.calculate_missing_gate_times() documents for that case. This test
constructs that ContestantTaskConfiguration row directly (rather than via the full compiler
pipeline, which requires a subtype-specific declared route unrelated to this bug) so it
reproduces exactly that "valid config with a stale payload" state.

Orchestrator.handle_event's AdaptiveStartEvent branch already recalculates absolute times and
persists them into predefined_gate_times (and pushes a transmit_contestant websocket message) -
that mechanism was never broken. What was missing is that nothing ever refreshed
compiled_gate_times_payload to match, so Contestant.gate_times kept preferring the stale
placeholder over the now-correct predefined_gate_times.
"""

import datetime
from queue import Queue
from unittest.mock import patch

from django.test import TestCase

from display.calculators.calculator import AdaptiveStartEvent
from display.calculators.calculator_utilities import round_time_minute
from display.calculators.orchestrator import Orchestrator
from display.default_scorecards.create_scorecards import create_scorecards
from display.models import (
    Aeroplane,
    Contest,
    Contestant,
    ContestantTaskConfiguration,
    Crew,
    EditableRoute,
    NavigationTask,
    Person,
    Route,
    Scorecard,
    Team,
)
from display.services.contestant_task_compiler import ContestantTaskCompiler
from display.utilities.gate_definitions import STARTINGPOINT, TURNPOINT
from display.utilities.navigation_task_type_definitions import PRECISION
from display.waypoint import Waypoint
from utilities.mock_utilities import TraccarMock


@patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
@patch("display.signals.get_traccar_instance", return_value=TraccarMock)
class TestAdaptiveStartGateTimesSync(TestCase):
    def setUp(self, *args):
        create_scorecards()
        precision_original = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.contest = Contest.objects.create(
            name="Adaptive start gate times sync test contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Adaptive", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ADPT"))

        def make_waypoint(name: str, waypoint_type: str = TURNPOINT) -> Waypoint:
            waypoint = Waypoint(name)
            waypoint.type = waypoint_type
            waypoint.gate_check = True
            waypoint.time_check = True
            return waypoint

        route = Route.objects.create(
            name="adaptive-start-route",
            waypoints=[make_waypoint("SP", STARTINGPOINT), make_waypoint("FP")],
        )
        navigation_task = NavigationTask.create(
            name="adaptive-start-task",
            contest=self.contest,
            route=route,
            original_scorecard=precision_original,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
        )
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="adaptive-start-contestant",
            contestant_number=1,
            adaptive_start=True,
        )

    def test_gate_times_reflect_absolute_times_after_adaptive_start_crossing(self, *args):
        # Reproduces the "valid config with a stale payload" state every contestant reaches
        # via ContestantTaskCompiler.compile() at declaration/creation time - before the
        # contestant ever starts flying, compiled_gate_times_payload holds the midnight-anchored
        # relative placeholder calculate_missing_gate_times() returns for adaptive-start
        # contestants with no start-time override.
        placeholder_gate_times = self.contestant.calculate_missing_gate_times({})
        self.assertIn("SP", placeholder_gate_times)
        self.assertEqual(placeholder_gate_times["SP"].date(), self.contestant.takeoff_time.date())
        self.assertLess(placeholder_gate_times["SP"].hour, 1)
        config = ContestantTaskConfiguration.objects.create(
            contestant=self.contestant,
            task_subtype=self.contestant.navigation_task.task_subtype or "",
            is_valid=True,
            compiled_gate_times_payload={key: value.isoformat() for key, value in placeholder_gate_times.items()},
        )

        self.assertEqual(self.contestant.gate_times["SP"], placeholder_gate_times["SP"])

        intersection_time = datetime.datetime(2026, 1, 1, 8, 5, 30, tzinfo=datetime.timezone.utc)
        absolute_gate_times = self.contestant.calculate_missing_gate_times({}, round_time_minute(intersection_time))
        self.assertNotEqual(absolute_gate_times["SP"], placeholder_gate_times["SP"])

        with patch("display.calculators.orchestrator.WebsocketFacade"):
            orchestrator = Orchestrator(self.contestant, Queue(), [], live_processing=False)
        event = AdaptiveStartEvent(intersection_time, position=None, gate_times=absolute_gate_times)
        orchestrator.handle_event(event)

        refreshed_contestant = Contestant.objects.get(pk=self.contestant.pk)
        refreshed_config = ContestantTaskConfiguration.objects.get(pk=config.pk)

        # predefined_gate_times was already correct before this fix - the bug was entirely in
        # compiled_gate_times_payload (and therefore the gate_times property) never catching up.
        # Compare the complete mappings (SP and FP), not just one gate - an implementation that
        # only refreshed the starting-point entry would pass a single-key assertion while later
        # gate times stayed stale.
        self.assertEqual(refreshed_contestant.predefined_gate_times, absolute_gate_times)
        self.assertEqual(
            {
                key: datetime.datetime.fromisoformat(value)
                for key, value in refreshed_config.compiled_gate_times_payload.items()
            },
            absolute_gate_times,
        )
        self.assertEqual(refreshed_contestant.gate_times, absolute_gate_times)


class TestAdaptiveStartCompileDoesNotRevertToPlaceholder(TestCase):
    """
    A second bug on top of the one above: even after compiled_gate_times_payload is correctly
    synced to the absolute times, ANY later call to ContestantTaskCompiler.compile() - e.g. the
    compiled_evidence endpoint, or a declaration PATCH - recomputed compiled_gate_times_payload
    from scratch via Contestant.calculate_missing_gate_times({}) with no start-time override. For
    an adaptive-start contestant that recomputation always reproduces the midnight-anchored
    placeholder, and compile() treats the mismatch against the now-correct persisted payload as
    drift needing a refresh - clobbering the real absolute times right back to the placeholder,
    even with force=False and nothing about the declaration having changed. This uses a real
    EditableRoute-backed task (like test_precision_navigation_takeoff_landing_gate_times.py) with
    no task_subtype, so ContestantTaskCompiler falls back to the trivially-valid legacy/base
    strategy - the same "valid config, identity gate times" shape the reported prod contestant
    (an ANR-family training task, not a declared 2.A2 precision task) was in.
    """

    @patch("display.models.contestant.get_traccar_instance", return_value=TraccarMock)
    @patch("display.signals.get_traccar_instance", return_value=TraccarMock)
    def setUp(self, *args):
        create_scorecards()
        self.scorecard = Scorecard.get_originals().get(shortcut_name="FAI Precision")
        self.editable_route = EditableRoute.objects.create(
            name="Adaptive start compile route",
            route={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"featureType": "route_path"},
                        "geometry": {"type": "LineString", "coordinates": [[11.0, 60.0], [11.1, 60.1], [11.2, 60.2]]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-1",
                            "name": "SP",
                            "pointType": "sp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 0,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.0, 60.0]},
                    },
                    {
                        "type": "Feature",
                        "properties": {
                            "id": "wp-2",
                            "name": "FP",
                            "pointType": "fp",
                            "featureType": "route_waypoint",
                            "width": 1852,
                            "isTiming": True,
                            "isPassing": True,
                            "sequence": 1,
                        },
                        "geometry": {"type": "Point", "coordinates": [11.2, 60.2]},
                    },
                ],
            },
        )
        self.route = self.editable_route.create_route(PRECISION, self.scorecard, None, None)

        self.contest = Contest.objects.create(
            name="Adaptive start compile contest",
            start_time=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc),
        )
        self.navigation_task = NavigationTask.create(
            name="adaptive-start-compile-task",
            contest=self.contest,
            route=self.route,
            editable_route=self.editable_route,
            original_scorecard=self.scorecard,
            start_time=datetime.datetime(2026, 1, 1, 6, tzinfo=datetime.timezone.utc),
            finish_time=datetime.datetime(2026, 1, 1, 16, tzinfo=datetime.timezone.utc),
        )
        crew = Crew.objects.create(member1=Person.objects.create(first_name="Adaptive", last_name="Pilot"))
        team = Team.objects.create(crew=crew, aeroplane=Aeroplane.objects.create(registration="LN-ADPT"))
        start_time = datetime.datetime(2026, 1, 1, 8, tzinfo=datetime.timezone.utc)
        self.contestant = Contestant.objects.create(
            navigation_task=self.navigation_task,
            team=team,
            takeoff_time=start_time,
            tracker_start_time=start_time - datetime.timedelta(minutes=30),
            finished_by_time=start_time + datetime.timedelta(hours=2),
            tracker_device_id="adaptive-start-compile-contestant",
            contestant_number=1,
            adaptive_start=True,
            air_speed=75,
            wind_direction=165,
            wind_speed=8,
        )

    def test_recompiling_after_crossing_does_not_revert_to_placeholder_times(self, *args):
        compiled = ContestantTaskCompiler(self.contestant).compile()
        self.assertTrue(compiled.is_valid, compiled.validation_errors)
        placeholder_gate_times = self.contestant.calculate_missing_gate_times({})
        self.assertEqual(
            datetime.datetime.fromisoformat(compiled.compiled_gate_times_payload["SP"]),
            placeholder_gate_times["SP"],
        )

        intersection_time = datetime.datetime(2026, 1, 1, 8, 5, 30, tzinfo=datetime.timezone.utc)
        absolute_gate_times = self.contestant.calculate_missing_gate_times({}, round_time_minute(intersection_time))
        self.assertNotEqual(absolute_gate_times["SP"], placeholder_gate_times["SP"])

        with patch("display.calculators.orchestrator.WebsocketFacade"):
            orchestrator = Orchestrator(self.contestant, Queue(), [], live_processing=False)
        event = AdaptiveStartEvent(intersection_time, position=None, gate_times=absolute_gate_times)
        orchestrator.handle_event(event)
        # StartingLinePassedEvent (fired alongside AdaptiveStartEvent in real crossings, see
        # gate_calculator.py's check_intersections) is what records the actual SP gate time -
        # reproduce that here rather than firing the full event, to keep this test focused on
        # the compile()-clobbering bug.
        self.contestant.record_actual_gate_time("SP", intersection_time)

        contestant = Contestant.objects.get(pk=self.contestant.pk)
        contestant.contestanttrack.calculator_started = True
        contestant.contestanttrack.current_state = "Enroute"
        contestant.contestanttrack.save(update_fields=["calculator_started", "current_state"])
        self.assertTrue(contestant.has_crossed_starting_line)

        recompiled = ContestantTaskCompiler(contestant).compile()
        self.assertEqual(
            datetime.datetime.fromisoformat(recompiled.compiled_gate_times_payload["SP"]),
            absolute_gate_times["SP"],
        )
        self.assertEqual(contestant.gate_times["SP"], absolute_gate_times["SP"])

    def test_routine_field_update_after_crossing_does_not_revert_predefined_gate_times(self, *args):
        # The more likely real-world trigger for the reported bug: ContestantSerialiser.update()
        # (src/display/serialisers.py) always pops "gate_times" from validated_data defaulting to
        # {} when the request body doesn't include it, and update_contestant_with_related_state
        # then does `instance.gate_times = parsed_gate_times; instance.save()` unconditionally -
        # i.e. every PATCH to a contestant, even one only touching an unrelated field like
        # contestant_number (allowed by Contestant.clean()'s guard even after calculator_started,
        # unlike takeoff_time/wind/adaptive_start/minutes_to_starting_point), runs the
        # Contestant.gate_times setter with an empty override. Before the calculate_missing_gate_times
        # fix, that silently reverted predefined_gate_times to the midnight-anchored placeholder -
        # with no explicit "compile" or declaration edit involved at all.
        from display.services.contestant_persistence import update_contestant_with_related_state

        intersection_time = datetime.datetime(2026, 1, 1, 8, 5, 30, tzinfo=datetime.timezone.utc)
        absolute_gate_times = self.contestant.calculate_missing_gate_times({}, round_time_minute(intersection_time))

        with patch("display.calculators.orchestrator.WebsocketFacade"):
            orchestrator = Orchestrator(self.contestant, Queue(), [], live_processing=False)
        event = AdaptiveStartEvent(intersection_time, position=None, gate_times=absolute_gate_times)
        orchestrator.handle_event(event)
        self.contestant.record_actual_gate_time("SP", intersection_time)

        contestant = Contestant.objects.get(pk=self.contestant.pk)
        contestant.contestanttrack.calculator_started = True
        contestant.contestanttrack.current_state = "Enroute"
        contestant.contestanttrack.save(update_fields=["calculator_started", "current_state"])
        self.assertTrue(contestant.has_crossed_starting_line)
        self.assertEqual(contestant.predefined_gate_times["SP"], absolute_gate_times["SP"])

        # An edit to a completely unrelated field, with no "gate_times" key in the request at
        # all - exactly what ContestantSerialiser.update() receives for e.g. a contestant number
        # correction after the flight.
        update_contestant_with_related_state(
            contestant,
            {"contestant_number": contestant.contestant_number + 1},
            gate_times=None,
            partial=True,
        )

        refreshed = Contestant.objects.get(pk=self.contestant.pk)
        self.assertEqual(refreshed.predefined_gate_times["SP"], absolute_gate_times["SP"])
