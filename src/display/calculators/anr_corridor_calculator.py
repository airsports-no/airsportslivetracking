import logging
from typing import List, Callable
import numpy as np
from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs

from display.calculators.calculator import Calculator
from display.calculators.positions_and_gates import Position, Gate
from display.models import Contestant, Scorecard, Route

logger = logging.getLogger(__name__)


class AnrCorridorCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    def passed_finishpoint(self, track: List["Position"], last_gate: "Gate"):
        position = track[-1]
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            self.corridor_state = self.INSIDE_CORRIDOR
            outside_time = (position.time - self.crossed_outside_time).total_seconds()
            penalty_time = outside_time - self.scorecard.get_corridor_grace_time(self.contestant)
            logger.info(
                "{} {}: Back inside the corridor after {} seconds".format(self.contestant, position.time,
                                                                          outside_time))
            if penalty_time > 0:
                penalty_time = np.round(penalty_time)
                self.update_score(last_gate,
                                  self.scorecard.get_corridor_outside_penalty(self.contestant) * penalty_time,
                                  "outside corridor ({} seconds)".format(int(penalty_time)),
                                  self.crossed_outside_position.latitude, self.crossed_outside_position.longitude,
                                  "anomaly", self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                                  maximum_score=self.scorecard.get_corridor_outside_maximum_penalty(
                                      self.contestant))

    def calculate_outside_route(self, track: List["Position"], last_gate: "Gate"):
        pass

    INSIDE_CORRIDOR = 0
    OUTSIDE_CORRIDOR = 1
    OUTSIDE_CORRIDOR_PENALTY_TYPE = "outside_corridor"

    def __init__(self, contestant: "Contestant", scorecard: "Scorecard", gates: List["Gate"], route: "Route",
                 update_score: Callable):
        super().__init__(contestant, scorecard, gates, route, update_score)
        self.corridor_state = self.INSIDE_CORRIDOR
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None
        self.pc = ccrs.PlateCarree()
        self.epsg = ccrs.epsg(3857)
        self.track_polygon = self.build_polygon()

    def build_polygon(self):
        points = []
        for waypoint in self.contestant.navigation_task.route.waypoints:
            if self.contestant.navigation_task.route.rounded_corners:
                points.extend(waypoint.left_corridor_line)
            else:
                points.append(waypoint.gate_line[0])
        for waypoint in reversed(self.contestant.navigation_task.route.waypoints):
            if self.contestant.navigation_task.route.rounded_corners:
                points.extend(list(reversed(waypoint.right_corridor_line)))
            else:
                points.append(waypoint.gate_line[1])
        points = np.array(points)
        print(points.shape)
        transformed_points = self.epsg.transform_points(self.pc, points[:, 0], points[:, 1])
        return Polygon(transformed_points)

    def _check_inside_polygon(self, latitude, longitude) -> bool:
        """
        Returns true if the point lies inside the corridor
        """
        x, y = self.epsg.transform_point(longitude, latitude, self.pc)
        p = Point(x, y)
        return self.track_polygon.contains(p)

    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        self.check_outside_corridor(track, last_gate)

    def check_outside_corridor(self, track: List["Position"], last_gate: "Gate"):
        position = track[-1]
        if not self._check_inside_polygon(position.latitude, position.longitude):
            # We are outside the corridor
            if self.corridor_state == self.INSIDE_CORRIDOR:
                logger.info(
                    "{} {}: Heading outside of corridor".format(self.contestant, position.time))

                self.crossed_outside_position = position
                self.corridor_state = self.OUTSIDE_CORRIDOR
                self.crossed_outside_time = position.time
        elif self.corridor_state == self.OUTSIDE_CORRIDOR:
            self.corridor_state = self.INSIDE_CORRIDOR
            outside_time = (position.time - self.crossed_outside_time).total_seconds()
            penalty_time = outside_time - self.scorecard.get_corridor_grace_time(self.contestant)
            logger.info(
                "{} {}: Back inside the corridor after {} seconds".format(self.contestant, position.time,
                                                                          outside_time))
            if penalty_time > 0:
                penalty_time = np.round(penalty_time)
                score = self.scorecard.get_corridor_outside_penalty(self.contestant) * penalty_time
                maximum_score = self.scorecard.get_corridor_outside_maximum_penalty(self.contestant)
                if maximum_score >= 0:
                    score = min(score, maximum_score)
                self.update_score(last_gate,
                                  score,
                                  "outside corridor ({} seconds)".format(int(penalty_time)),
                                  self.crossed_outside_position.latitude, self.crossed_outside_position.longitude,
                                  "anomaly", self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                                  maximum_score=-1)
