import datetime
import logging
from multiprocessing.queues import Queue
from typing import List, Callable

from display.calculators.calculator_utilities import PolygonHelper
from display.calculators.gatekeeper import Gatekeeper
from display.models import Contestant, PlayingCard

logger = logging.getLogger(__name__)


class GatekeeperPoker(Gatekeeper):
    def __init__(
            self, contestant: "Contestant", calculators: List[Callable], live_processing: bool = True,
            queue_name_override: str = None
    ):
        super().__init__(contestant, calculators, live_processing, queue_name_override=queue_name_override)
        logger.info(f"Starting the GatekeeperPoker for contestant {self.contestant}")
        self.gate_polygons = []
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude)
        self.waypoint_names = [gate.name for gate in self.contestant.navigation_task.route.waypoints]
        gates = self.contestant.navigation_task.route.prohibited_set.filter(type="gate")
        for gate in gates:
            self.gate_polygons.append((gate.name, self.polygon_helper.build_polygon(gate.path)))
        # Sort list of polygons according to list of waypoint names
        self.sorted_polygons = [
            (polygon_name, polygon, index)
            for index, gate_name in enumerate(self.waypoint_names)
            for polygon_name, polygon in self.gate_polygons
            if polygon_name == gate_name
        ]
        self.first_gate = True
        self.first_finish = True

    def notify_termination(self):
        super().notify_termination()
        self.contestant.contestanttrack.updates_current_state("Finished")

    def check_termination(self):
        super().check_termination()
        already_terminated = self.track_terminated
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.live_processing and now > self.contestant.finished_by_time:
            if not already_terminated:
                logger.info(
                    f"{self.contestant}: {'Live processing' if self.live_processing else 'Offline processing'} {'past finish time' if datetime.datetime.now(datetime.timezone.utc) > self.contestant.finished_by_time else ''}, terminating"
                )
                self.notify_termination()

    def check_gates(self):
        if len(self.sorted_polygons) > 0:
            position = self.track[-1]
            polygon_name, polygon, waypoint_index = self.sorted_polygons[0]
            inside = self.polygon_helper.check_inside_polygons(
                [(polygon_name, polygon)], position.latitude, position.longitude
            )
            if len(inside) > 0:
                PlayingCard.add_contestant_card(
                    self.contestant, PlayingCard.get_random_unique_card(self.contestant), polygon_name, waypoint_index
                )
                self.sorted_polygons.pop(0)
                if self.first_gate:
                    self.contestant.contestanttrack.updates_current_state("Tracking")
                    self.first_gate = False
