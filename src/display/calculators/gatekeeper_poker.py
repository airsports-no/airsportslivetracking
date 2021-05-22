import datetime
import logging
from multiprocessing.queues import Queue
from typing import List, Callable

from display.calculators.calculator_utilities import PolygonHelper
from display.calculators.gatekeeper import Gatekeeper
from display.models import Contestant, PlayingCard

logger = logging.getLogger(__name__)


class GatekeeperPoker(Gatekeeper):
    def __init__(self, contestant: "Contestant", position_queue: Queue, calculators: List[Callable],
                 live_processing: bool = True):
        super().__init__(contestant, position_queue, calculators, live_processing)
        logger.info(f"Starting the GatekeeperPoker for contestant {self.contestant}")
        self.gate_polygons = {}
        self.polygon_helper = PolygonHelper()
        self.waypoint_names = [gate.name for gate in self.contestant.navigation_task.route.waypoints]
        gates = self.contestant.navigation_task.route.prohibited_set.filter(type="gate")
        for gate in gates:
            self.gate_polygons[gate.name] = self.polygon_helper.build_polygon(gate)
        # Sort list of polygons according to list of waypoint names
        self.sorted_polygons = [(polygon_name, polygon, index) for index, gate_name in enumerate(self.waypoint_names)
                                for
                                polygon_name, polygon in self.gate_polygons.items() if polygon_name == gate_name]
        self.first_gate = True

    def check_termination(self):
        super().check_termination()
        already_terminated = self.track_terminated
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            if not already_terminated:
                logger.info(f"{self.contestant}: Live processing and past finish time, terminating")
            self.track_terminated = True
            self.contestant.contestanttrack.updates_current_state("Finished")

    def check_gates(self):
        if len(self.sorted_polygons) > 0:
            position = self.track[-1]
            polygon_name, polygon, waypoint_index = self.sorted_polygons[0]
            inside = self.polygon_helper.check_inside_polygons({polygon_name: polygon}, position.latitude,
                                                               position.longitude)
            if len(inside) > 0:
                PlayingCard.add_contestant_card(self.contestant, PlayingCard.get_random_unique_card(self.contestant),
                                                polygon_name, waypoint_index)
                self.sorted_polygons.pop(0)
                if self.first_gate:
                    self.contestant.contestanttrack.updates_current_state("Tracking")
                    self.first_gate = False
