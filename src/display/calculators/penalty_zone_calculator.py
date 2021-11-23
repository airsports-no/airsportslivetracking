import logging
from typing import List, Callable, Optional
import numpy as np
from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs

from display.calculators.calculator import Calculator
from display.calculators.calculator_utilities import PolygonHelper
from display.calculators.positions_and_gates import Position, Gate
from display.models import Contestant, Scorecard, Route, INFORMATION, ANOMALY

logger = logging.getLogger(__name__)


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
                (zone.name, self.polygon_helper.build_polygon(zone))
            )

    def calculate_enroute(
        self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"
    ):
        self.check_inside_prohibited_zone(track, last_gate)

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
            else:
                self.existing_reference[zone] = self.update_score(
                    last_gate or self.gates[0],
                    self.scorecard.calculate_penalty_zone_score(
                        self.contestant, start_time, position.time
                    ),
                    "inside penalty zone {}".format(zone),
                    position.latitude,
                    position.longitude,
                    ANOMALY,
                    self.INSIDE_PENALTY_ZONE_PENALTY_TYPE,
                    existing_reference=self.existing_reference.get(zone),
                )
