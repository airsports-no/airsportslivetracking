import logging
from typing import List, Callable, Optional
import numpy as np
from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import PolygonHelper
from display.calculators.positions_and_gates import Position, Gate
from display.coordinate_utilities import bearing_difference
from display.models import Contestant, Scorecard, Route, INFORMATION, ANOMALY

logger = logging.getLogger(__name__)

LOOKAHEAD_SECONDS = 30


class PenaltyZoneCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    def passed_finishpoint(self, track: List["Position"], last_gate: "Gate"):
        pass

    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        self.check_inside_prohibited_zone(track, last_gate)

    INSIDE_PENALTY_ZONE_PENALTY_TYPE = "inside_penalty_zone"

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
        self.running_penalty = {}
        self.gates = gates
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude)
        self.zone_polygons = []
        self.entered_polygon_times = {}
        self.existing_reference = {}
        zones = route.prohibited_set.filter(type="penalty")
        for zone in zones:
            self.zone_polygons.append(
                (zone.name, self.polygon_helper.build_polygon(zone.path))
            )

    def get_danger_level(self, position: "Position") -> float:
        """
        Danger level ranges from 0 to 100 where 100 is outside the corridor, and all other numbers represent half seconds
        :param position:
        :return:
        """
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            return 100
        return min([99, 2 * (self._distance_from_point_to_polygons(position.latitude,
                                                                   position.longitude) / 1852) / position.speed])

    def calculate_danger_level(self, track: List["Position"]) -> float:
        """
        Danger level ranges from 0 to 100 where 100 is inside a penalty zone
        """
        distance_danger = 0
        if len(track) > 0:
            distances = self.polygon_helper.distance_from_point_to_polygons(self.zone_polygons, track[-1].latitude,
                                                                            track[-1].longitude)
            minimum_distance = min(list(distances.values()))
            minimum_time = minimum_distance / (track[-1].speed * 1852)
            distance_danger = min([50, 2 * minimum_time])
        if len(track) > 3:
            turning_rate = bearing_difference(track[-1].course, track[-3].course) / (
                    track[-1].time - track[-3].time).total_seconds()
            intersection_times = self.polygon_helper.time_to_intersection(self.zone_polygons, track[-1].latitude,
                                                                          track[-1].longitude, track[-1].course,
                                                                          track[-1].speed, turning_rate,
                                                                          LOOKAHEAD_SECONDS)
            shortest_time = min(list(intersection_times.values()))
            distance_danger = max([distance_danger, 99 * shortest_time / LOOKAHEAD_SECONDS])
        return distance_danger

    def report_danger_level(self, track: List["Position"]):
        if len(self.entered_polygon_times) > 0:
            danger_level = 100
        else:
            danger_level = self.calculate_danger_level(track)
        self.websocket_facade.transmit_danger_estimate_and_accumulated_penalty(self.contestant, danger_level,
                                                                               self.running_penalty)

    def calculate_enroute(
            self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"
    ):
        self.check_inside_prohibited_zone(track, last_gate)
        self.report_danger_level(track)

    def check_inside_prohibited_zone(
            self, track: List["Position"], last_gate: Optional["Gate"]
    ):
        position = track[-1]
        currently_inside = self.polygon_helper.check_inside_polygons(
            self.zone_polygons, position.latitude, position.longitude
        )
        for inside in currently_inside:
            if inside not in self.entered_polygon_times:
                self.entered_polygon_times[inside] = position.time

        for zone, start_time in dict(self.entered_polygon_times).items():
            if zone not in currently_inside:
                del self.entered_polygon_times[zone]
                self.update_score(
                    last_gate or self.gates[0],
                    0,
                    "exited penalty zone {}".format(zone),
                    position.latitude,
                    position.longitude,
                    INFORMATION,
                    self.INSIDE_PENALTY_ZONE_PENALTY_TYPE,
                )
                del self.existing_reference[zone]
                del self.running_penalty[zone]
            else:
                self.running_penalty[zone] = self.scorecard.calculate_penalty_zone_score(
                    self.contestant, start_time, position.time
                )
                self.existing_reference[zone] = self.update_score(
                    last_gate or self.gates[0],
                    self.running_penalty[zone],
                    "inside penalty zone {}".format(zone),
                    position.latitude,
                    position.longitude,
                    ANOMALY,
                    self.INSIDE_PENALTY_ZONE_PENALTY_TYPE,
                    existing_reference=self.existing_reference.get(zone),
                )
