import datetime
import logging
from typing import List, Callable

from display.calculators.gatekeeper import Gatekeeper
from display.calculators.positions_and_gates import Gate, MultiGate
from display.utilities.route_building_utilities import calculate_extended_gate
from display.utilities.coordinate_utilities import Projector
from display.models import Contestant, ANOMALY

logger = logging.getLogger(__name__)

LOOP_TIME = 60


class GatekeeperLanding(Gatekeeper):
    """
    Gatekeeper to track rounds in the landing pattern by counting each time the contestant crosses the landing gate.
    The contestants score reflects the number of rounds in the patent.
    """
    def __init__(self, contestant: "Contestant", calculators: List[Callable],
                 live_processing: bool = True, queue_name_override: str = None):
        super().__init__(contestant, calculators, live_processing, queue_name_override=queue_name_override)
        self.last_intersection = None
        self.landing_gate = MultiGate([Gate(landing_gate,
                                            self.contestant.gate_times[landing_gate.name],
                                            calculate_extended_gate(landing_gate, self.scorecard)) for landing_gate in
                                       self.contestant.navigation_task.route.landing_gates])
        self.projector = Projector(self.landing_gate.gates[0].latitude, self.landing_gate.gates[0].longitude)
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
                    self.update_score(self.landing_gate.gates[0], 1, "passed landing line", self.track[-1].latitude,
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
