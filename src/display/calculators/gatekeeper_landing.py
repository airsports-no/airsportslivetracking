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
from display.models import ContestantTrack, Contestant
from display.waypoint import Waypoint

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class ScoreAccumulator:
    def __init__(self):
        self.related_score = {}

    def set_and_update_score(self, score: float, score_type: str, maximum_score: Optional[float]) -> float:
        """
        Returns the calculated score given the maximum limits. If there is no maximum limit, score is returned
        """
        current_score_for_type = self.related_score.setdefault(score_type, 0)
        if maximum_score is not None and maximum_score > -1:
            if current_score_for_type + score >= maximum_score:
                score = maximum_score - current_score_for_type
        self.related_score[score_type] += score
        return score


LOOP_TIME = 60


class GatekeeperLanding(Gatekeeper):
    def __init__(self, contestant: "Contestant", position_queue: Queue, calculators: List[Callable],
                 live_processing: bool = True):
        super().__init__(contestant, position_queue, calculators, live_processing)
        self.last_intersection = None
        self.accumulated_scores = ScoreAccumulator()
        self.landing_gate = Gate(self.contestant.navigation_task.route.landing_gate,
                                 datetime.datetime.min,
                                 calculate_extended_gate(self.contestant.navigation_task.route.landing_gate,
                                                         self.scorecard,
                                                         self.contestant)) if self.contestant.navigation_task.route.landing_gate else None
        self.projector = Projector(self.landing_gate.latitude, self.landing_gate.longitude)
        for calculator in calculators:
            self.calculators.append(
                calculator(self.contestant, self.scorecard, self.gates, self.contestant.navigation_task.route,
                           self.update_score))

    def check_intersections(self):
        if self.landing_gate is not None:
            intersection_time = self.landing_gate.get_gate_intersection_time(self.projector, self.track)
            if intersection_time:
                if self.last_intersection is None or intersection_time > self.last_intersection + datetime.timedelta(
                        seconds=30):
                    self.update_score(self.landing_gate, 1, "passed landing line", self.track[-1].latitude,
                                      self.track[-1].longitude, "information", "landing_line")
                    self.contestant.contestanttrack.update_gate_time(self.landing_gate.name, intersection_time)

    def check_termination(self):
        already_terminated = self.track_terminated
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            if not already_terminated:
                logger.info("Live processing and past finish time, terminating")
            self.track_terminated = True
        if self.track_terminated:
            self.contestant.contestanttrack.set_calculator_finished()

    def check_gates(self):
        self.check_intersections()
