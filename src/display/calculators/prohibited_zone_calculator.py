import logging
from typing import List, Callable, Optional
import numpy as np
from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import PolygonHelper, get_shortest_intersection_time
from display.calculators.positions_and_gates import Position, Gate
from display.coordinate_utilities import bearing_difference
from display.models import Contestant, Scorecard, Route

logger = logging.getLogger(__name__)


class ProhibitedZoneCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    def passed_finishpoint(self, track: List["Position"], last_gate: "Gate"):
        pass

    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        self.check_inside_prohibited_zone(track, last_gate)

    INSIDE_PROHIBITED_ZONE_PENALTY_TYPE = "inside_prohibited_zone"

    def __init__(
            self,
            contestant: "Contestant",
            scorecard: "Scorecard",
            gates: List["Gate"],
            route: "Route",
            update_score: Callable,
            type_filter: str = None,
    ):
        super().__init__(contestant, scorecard, gates, route, update_score)
        self.inside_zones = set()
        self.gates = gates
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude)
        self.zone_polygons = []
        self.running_penalty = {}
        zones = route.prohibited_set.filter(type="prohibited")
        for zone in zones:
            self.zone_polygons.append((zone.name, self.polygon_helper.build_polygon(zone.path)))

    def _calculate_danger_level(self, track: List["Position"]) -> float:
        """
        Danger level ranges from 0 to 100 where 100 is inside a prohibited zone
        """
        LOOKAHEAD_SECONDS = 40
        shortest_time = get_shortest_intersection_time(track, self.polygon_helper, self.zone_polygons,
                                                       LOOKAHEAD_SECONDS)
        return 99 * (LOOKAHEAD_SECONDS - shortest_time) / LOOKAHEAD_SECONDS

    def get_danger_level_and_accumulated_score(self, track: List["Position"]):
        # return 0, 0
        if len(self.inside_zones) > 0:
            return 100, sum([0] + list(self.running_penalty.values()))
        else:
            return self._calculate_danger_level(track), sum([0] + list(self.running_penalty.values()))

    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        self.check_inside_prohibited_zone(track, last_gate)

    def check_inside_prohibited_zone(self, track: List["Position"], last_gate: Optional["Gate"]):
        position = track[-1]
        inside_this_time = set()
        for inside in self.polygon_helper.check_inside_polygons(
                self.zone_polygons, position.latitude, position.longitude
        ):
            inside_this_time.add(inside)
            if inside not in self.inside_zones:
                penalty = self.scorecard.get_prohibited_zone_penalty(self.contestant)
                self.running_penalty[inside] = penalty
                self.update_score(
                    last_gate or self.gates[0],
                    penalty,
                    "entered prohibited zone {}".format(inside),
                    position.latitude,
                    position.longitude,
                    "anomaly",
                    self.INSIDE_PROHIBITED_ZONE_PENALTY_TYPE,
                )
        for zone in self.inside_zones:
            if zone not in inside_this_time:
                del self.running_penalty[zone]
        self.inside_zones = inside_this_time
