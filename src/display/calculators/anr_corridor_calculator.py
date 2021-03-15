import matplotlib.pyplot as plt
import logging
from typing import List, Callable
import numpy as np
from cartopy.io.img_tiles import OSM
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
            self.check_and_apply_outside_penalty(position, last_gate)
            self.corridor_state = self.INSIDE_CORRIDOR

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
        self.last_gate_missed_position = None
        self.previous_last_gate = None
        self.crossed_outside_position = None
        self.pc = ccrs.PlateCarree()
        self.epsg = ccrs.epsg(3857)
        self.track_polygon = self.build_polygon()
        self.plot_polygon()

    def build_polygon(self):
        points = []
        for waypoint in self.contestant.navigation_task.route.waypoints:
            if self.contestant.navigation_task.route.rounded_corners and waypoint.left_corridor_line is not None:
                points.extend(waypoint.left_corridor_line)
            else:
                points.append(waypoint.gate_line[0])
        for waypoint in reversed(self.contestant.navigation_task.route.waypoints):
            if self.contestant.navigation_task.route.rounded_corners and waypoint.right_corridor_line is not None:
                points.extend(list(reversed(waypoint.right_corridor_line)))
            else:
                points.append(waypoint.gate_line[1])
        points = np.array(points)
        print(points.shape)
        print(points)
        transformed_points = self.epsg.transform_points(self.pc, points[:, 1], points[:, 0])
        return Polygon(transformed_points)

    def plot_polygon(self):
        # imagery = OSM()
        ax = plt.axes(projection=self.epsg)
        # ax.add_image(imagery, 8)
        ax.set_aspect("auto")
        ax.plot(self.track_polygon.boundary.xy[0], self.track_polygon.boundary.xy[1])
        ax.add_geometries([self.track_polygon], crs=self.epsg, facecolor="blue", alpha=0.4)
        plt.savefig("polygon.png", dpi=100)

    def _check_inside_polygon(self, latitude, longitude) -> bool:
        """
        Returns true if the point lies inside the corridor
        """
        x, y = self.epsg.transform_point(longitude, latitude, self.pc)
        p = Point(x, y)
        return self.track_polygon.contains(p)

    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        self.check_outside_corridor(track, last_gate)

    def missed_gate(self, gate: Gate, position: Position):
        if position == self.last_gate_missed_position:
            # If we are at the same position as the last missed the State it means that we are missing several gates
            # in a row. We need to apply maximum penalty for each leg
            self.check_and_apply_outside_penalty(position, gate, apply_maximum_penalty=True)
        else:
            self.check_and_apply_outside_penalty(position, gate)
        self.last_gate_missed_position = position

    def check_and_apply_outside_penalty(self, position: "Position", last_gate: Gate,
                                        apply_maximum_penalty: bool = False):
        outside_time = (position.time - self.crossed_outside_time).total_seconds()
        penalty_time = outside_time - self.scorecard.get_corridor_grace_time(self.contestant)
        logger.info(
            "{} {}: Back inside the corridor after {} seconds".format(self.contestant, position.time,
                                                                      outside_time))
        if penalty_time > 0:
            penalty_time = np.round(penalty_time)
            score = self.scorecard.get_corridor_outside_penalty(self.contestant) * penalty_time
            if apply_maximum_penalty:
                score = self.scorecard.get_corridor_outside_maximum_penalty(self.contestant)
            # If this is called when we have crossed a gate, we need to reset the outside time to Grace time before now to start counting new points
            self.crossed_outside_time = position.time - self.scorecard.get_corridor_grace_time(self.contestant)
            self.crossed_outside_position = position
            self.update_score(last_gate,
                              score,
                              "outside corridor ({} seconds)".format(int(penalty_time)),
                              self.crossed_outside_position.latitude, self.crossed_outside_position.longitude,
                              "anomaly", self.OUTSIDE_CORRIDOR_PENALTY_TYPE + last_gate.name,
                              maximum_score=self.scorecard.get_corridor_outside_maximum_penalty(self.contestant))

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
            else:
                if last_gate != self.previous_last_gate:
                    self.check_and_apply_outside_penalty(position, last_gate)
        elif self.corridor_state == self.OUTSIDE_CORRIDOR:
            self.corridor_state = self.INSIDE_CORRIDOR
            self.check_and_apply_outside_penalty(position, last_gate)
