import datetime
import logging
import threading
from multiprocessing.queues import Queue
from typing import List, TYPE_CHECKING, Optional, Callable

import pytz

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import round_time, distance_between_gates
from display.calculators.gatekeeper import Gatekeeper
from display.calculators.positions_and_gates import Gate, Position
from display.convert_flightcontest_gpx import calculate_extended_gate
from display.coordinate_utilities import line_intersect, fraction_of_leg, Projector, calculate_distance_lat_lon, \
    calculate_fractional_distance_point_lat_lon
from display.models import ContestantTrack, Contestant, ANOMALY
from display.waypoint import Waypoint

logger = logging.getLogger(__name__)

LOOP_TIME = 60


class GatekeeperLanding(Gatekeeper):
    def __init__(self, contestant: "Contestant", calculators: List[Callable],
                 live_processing: bool = True, queue_name_override: str=None):
        super().__init__(contestant, calculators, live_processing, queue_name_override=queue_name_override)
        self.last_intersection = None
        self.landing_gate = Gate(self.contestant.navigation_task.route.landing_gates,
                                 datetime.datetime.min,
                                 calculate_extended_gate(self.contestant.navigation_task.route.landing_gates,
                                                         self.scorecard)) if self.contestant.navigation_task.route.landing_gates else None
        self.projector = Projector(self.landing_gate.latitude, self.landing_gate.longitude)
        for calculator in calculators:
            self.calculators.append(
                calculator(self.contestant, self.scorecard, self.gates, self.contestant.navigation_task.route,
                           self.update_score))

    def check_intersections(self):
        if self.landing_gate is not None:
            intersection_time = self.landing_gate.get_gate_intersection_time(self.projector, self.track)
            if intersection_time:
                self.contestant.contestanttrack.updates_current_state("Tracking")
                if self.last_intersection is None or intersection_time > self.last_intersection + datetime.timedelta(
                        seconds=30):
                    self.last_intersection = intersection_time
                    self.update_score(self.landing_gate, 1, "passed landing line", self.track[-1].latitude,
                                      self.track[-1].longitude, ANOMALY, "landing_line")

    def check_termination(self):
        super().check_termination()
        already_terminated = self.track_terminated
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            if not already_terminated:
                self.notify_termination()

    def check_gates(self):
        self.check_intersections()
