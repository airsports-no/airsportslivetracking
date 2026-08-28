"""Shared synthetic-test helpers for the scoring calculators.

These build minimal, hand-constructed positions/waypoints/state in memory -
no DB rows, no fixture files, no ContestantProcessor/Orchestrator/Redis - so
calculator state machines can be exercised directly and deterministically.

This consolidates the create_position/waypoint-mock pattern that was
independently copy-pasted across several test files (most fully in
CalculatorUnitTestBase, test_calculators_unit.py:30). New synthetic test
files should build on SyntheticCalculatorTestBase below rather than
re-deriving this scaffolding again.
"""

import datetime
from queue import Empty
from unittest.mock import MagicMock, patch

from django.test import TestCase

from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.coordinate_utilities import Projector


def make_position(projector, lat, lon, time, *, altitude=0.0, speed=0.0, course=0.0):
    """Build a MagicMock position with real projected coordinates from `projector`.

    This is the canonical position builder for synthetic calculator tests -
    it produces something that satisfies calculator code reading
    latitude/longitude/time/projected_x/projected_y/altitude/speed/course,
    without needing a real ContestantReceivedPosition DB row.
    """
    if time.tzinfo is None:
        time = time.replace(tzinfo=datetime.timezone.utc)
    pos = MagicMock(spec=ContestantReceivedPosition)
    pos.latitude = float(lat)
    pos.longitude = float(lon)
    pos.time = time
    pos.altitude = altitude
    pos.speed = speed
    pos.course = course
    proj = projector.project_point(pos.latitude, pos.longitude)
    pos.projected_x = proj.projected_x
    pos.projected_y = proj.projected_y
    return pos


def make_waypoint(**overrides):
    """Build a MagicMock waypoint/gate pre-populated with the attributes a
    Gate (and the calculators that read waypoints directly) need. Override
    any field via kwargs, e.g. make_waypoint(name="TP1", type="tp").
    """
    waypoint = MagicMock()
    defaults = dict(
        latitude=60.0,
        longitude=11.0,
        name="WP",
        type="tp",
        width=100.0,
        gate_line=((60.0, 11.0), (60.0, 11.1)),
        gate_line_infinite=((60.0, 11.0), (60.0, 11.1)),
        gate_line_extended=((60.0, 11.0), (60.0, 11.1)),
        bearing=0,
        bearing_from_previous=0,
        bearing_next=0,
        center_x=0.0,
        center_y=0.0,
        inside_distance=500,
        outside_distance=1000,
        gate_check=True,
        time_check=True,
        is_procedure_turn=False,
        is_steep_turn=False,
        on_curved_segment=False,
        infinite_passing_time=None,
        passing_time=None,
        missed=False,
        is_visible=True,
    )
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(waypoint, key, value)
    return waypoint


class SyntheticCalculatorTestBase(TestCase):
    """Base for calculator unit tests driven entirely by hand-built state -
    no DB rows, no fixture files, no ContestantProcessor/Orchestrator.

    Subclasses build a calculator directly (Calculator(contestant, scorecard,
    route, score_processing_queue, live_processing=False, projector=...)) and
    drive it via its public calculate_enroute/on_*/finalise methods, reading
    results back via drain_queue() or by patching update_score directly.
    """

    def setUp(self):
        self.projector = Projector(60, 11)
        # Gate.pre_project touches real geometry helpers that assume a fully
        # populated Waypoint; synthetic tests don't need real projected gate
        # geometry, so this is patched globally like CalculatorUnitTestBase does.
        self.pre_project_patcher = patch("display.calculators.positions_and_gates.Gate.pre_project")
        self.mock_pre_project = self.pre_project_patcher.start()

    def tearDown(self):
        self.pre_project_patcher.stop()

    def make_position(self, lat, lon, time, **kwargs):
        return make_position(self.projector, lat, lon, time, **kwargs)

    def make_waypoint(self, **overrides):
        return make_waypoint(**overrides)

    def drain_queue(self, queue):
        """Return all UpdateScoreMessages from `queue`, in emission order,
        whether it's a real Queue/queue.Queue or a MagicMock."""
        if isinstance(queue, MagicMock):
            return [c.args[0] for c in queue.put_nowait.call_args_list]
        messages = []
        while True:
            try:
                messages.append(queue.get_nowait())
            except Empty:
                break
        return messages
