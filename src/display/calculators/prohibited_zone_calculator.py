import logging
from datetime import timedelta
from multiprocessing import Queue
from typing import List, Optional

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import PolygonHelper, get_shortest_intersection_time
from display.calculators.positions_and_gates import Position, Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route

logger = logging.getLogger(__name__)


class ProhibitedZoneCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    INSIDE_PROHIBITED_ZONE_PENALTY_TYPE = "inside_prohibited_zone"

    def __init__(
        self,
        contestant: "Contestant",
        scorecard: "Scorecard",
        gates: List["Gate"],
        route: "Route",
        score_processing_queue: Queue,
    ):
        super().__init__(contestant, scorecard, gates, route, score_processing_queue)
        self.inside_zones = {}
        self.zones_scored = set()
        self.gates = gates
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude)
        self.zone_polygons = []
        self.running_penalty = {}
        self.zone_map = {}
        self.prohibited_zone_grace_time = timedelta(seconds=self.scorecard.prohibited_zone_grace_time)
        zones = route.prohibited_set.filter(type="prohibited")
        for zone in zones:
            self.zone_map[zone.pk] = zone
            self.zone_polygons.append((zone.pk, self.polygon_helper.build_polygon(zone.path)))

    def passed_finishpoint(self, track: List["Position"], last_gate: "Gate"):
        pass

    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        self.check_inside_prohibited_zone(track, last_gate)

    def _calculate_danger_level(self, track: List["Position"]) -> float:
        """
        Danger level ranges from 0 to 100 where 100 is inside a prohibited zone
        """
        LOOKAHEAD_SECONDS = 40
        shortest_time = get_shortest_intersection_time(
            track, self.polygon_helper, self.zone_polygons, LOOKAHEAD_SECONDS
        )
        return 99 * (LOOKAHEAD_SECONDS - shortest_time) / LOOKAHEAD_SECONDS

    def get_danger_level_and_accumulated_score(self, track: List["Position"]):
        # return 0, 0
        if len(self.inside_zones) > 0:
            return 100, sum([0] + list(self.running_penalty.values()))
        else:
            return self._calculate_danger_level(track), sum([0] + list(self.running_penalty.values()))

    def calculate_enroute(
        self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate", next_gate: Optional["Gate"]
    ):
        self.check_inside_prohibited_zone(track, last_gate)

    def check_inside_prohibited_zone(self, track: List["Position"], last_gate: Optional["Gate"]):
        position = track[-1]
        inside_this_time = set()
        for zone_pk in self.polygon_helper.check_inside_polygons(
            self.zone_polygons, position.latitude, position.longitude
        ):
            inside_this_time.add(zone_pk)
            if zone_pk not in self.inside_zones:
                self.inside_zones[zone_pk] = position.time
            if (
                zone_pk not in self.zones_scored
                and position.time > self.inside_zones[zone_pk] + self.prohibited_zone_grace_time
            ):
                self.zones_scored.add(zone_pk)
                penalty = self.scorecard.prohibited_zone_penalty
                self.running_penalty[zone_pk] = penalty
                self.update_score(
                    UpdateScoreMessage(
                        position.time,
                        last_gate or self.gates[0],
                        penalty,
                        "entered prohibited zone {}".format(self.zone_map[zone_pk].name),
                        position.latitude,
                        position.longitude,
                        "anomaly",
                        self.INSIDE_PROHIBITED_ZONE_PENALTY_TYPE,
                    )
                )
        for zone in list(self.inside_zones.keys()):
            if zone not in inside_this_time:
                try:
                    del self.running_penalty[zone]
                except KeyError:
                    pass
                del self.inside_zones[zone]
                try:
                    self.zones_scored.remove(zone)
                except KeyError:
                    pass
