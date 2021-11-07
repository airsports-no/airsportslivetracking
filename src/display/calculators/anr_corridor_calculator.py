import datetime

import matplotlib.pyplot as plt
import logging
from typing import List, Callable, Optional
import numpy as np
from cartopy.io.img_tiles import OSM
from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs

from display.calculators.calculator import Calculator
from display.calculators.positions_and_gates import Position, Gate
from display.coordinate_utilities import utm_from_lat_lon
from display.models import Contestant, Scorecard, Route

logger = logging.getLogger(__name__)


class AnrCorridorCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    def passed_finishpoint(self, track: List["Position"], last_gate: "Gate"):
        position = track[-1]
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            self.check_and_apply_outside_penalty(position, self.crossed_outside_gate or last_gate)
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
        self.previous_corridor_state = self.INSIDE_CORRIDOR
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.last_gate_missed_position = None
        self.previous_last_gate = None
        self.crossed_outside_position = None
        self.crossed_outside_gate = None
        self.corridor_grace_time = self.scorecard.get_corridor_grace_time(self.contestant)
        self.pc = ccrs.PlateCarree()
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.utm = utm_from_lat_lon(waypoint.latitude, waypoint.longitude)
        self.track_polygon = self.build_polygon()
        self.existing_reference = None
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
        transformed_points = self.utm.transform_points(self.pc, points[:, 1], points[:, 0])
        return Polygon(transformed_points)

    def plot_polygon(self):
        # imagery = OSM()
        ax = plt.axes(projection=self.utm)
        # ax.add_image(imagery, 8)
        ax.set_aspect("auto")
        ax.plot(self.track_polygon.boundary.xy[0], self.track_polygon.boundary.xy[1])
        ax.add_geometries([self.track_polygon], crs=self.utm, facecolor="blue", alpha=0.4)
        plt.savefig("polygon.png", dpi=100)

    def _check_inside_polygon(self, latitude, longitude) -> bool:
        """
        Returns true if the point lies inside the corridor
        """
        x, y = self.utm.transform_point(longitude, latitude, self.pc)
        p = Point(x, y)
        return self.track_polygon.contains(p)

    def calculate_enroute(self, track: List["Position"], last_gate: "Gate", in_range_of_gate: "Gate"):
        self.check_outside_corridor(track, last_gate)

    def missed_gate(self, previous_gate: Optional[Gate], gate: Gate, position: Position):
        if self.crossed_outside_time is None:
            return
        penalty_gate = previous_gate or gate
        # Reset scoring to start counting again, but this time without grace time since we might be outside
        outside_time = (position.time - self.crossed_outside_time).total_seconds()
        self.crossed_outside_position = position
        self.crossed_outside_time = position.time
        # Correct for any remaining grace time if we exited the corridor immediately before the gate
        self.corridor_grace_time = max(0, self.corridor_grace_time - outside_time)
        self.existing_reference = None

        if position == self.last_gate_missed_position:
            # If we are at the same position as the last missed the gate it means that we are missing several gates
            # in a row. We need to apply maximum penalty for each leg
            self.check_and_apply_outside_penalty(position, penalty_gate, apply_maximum_penalty=True)
        self.last_gate_missed_position = position

    def check_and_apply_outside_penalty(self, position: "Position", last_gate: Gate,
                                        apply_maximum_penalty: bool = False):
        if self.crossed_outside_time is None or last_gate is None:
            return
        outside_time = (position.time - self.crossed_outside_time).total_seconds()
        penalty_time = np.round(outside_time - self.corridor_grace_time)
        score = self.scorecard.get_corridor_outside_penalty(
            self.contestant) * penalty_time if outside_time > self.corridor_grace_time else 0
        if apply_maximum_penalty:
            score = max(self.scorecard.get_corridor_maximum_penalty(self.contestant), 0)
        # If this is called when we have crossed a gate, we need to reset the outside time to Grace time before now to start counting new points
        if self.corridor_state == self.OUTSIDE_CORRIDOR or apply_maximum_penalty:
            self.existing_reference = self.update_score(last_gate,
                                                        score,
                                                        "outside corridor ({} s)".format(int(outside_time)),
                                                        self.crossed_outside_position.latitude,
                                                        self.crossed_outside_position.longitude,
                                                        "anomaly",
                                                        f"{self.OUTSIDE_CORRIDOR_PENALTY_TYPE}_{last_gate.name}",
                                                        maximum_score=self.scorecard.get_corridor_maximum_penalty(
                                                            self.contestant),
                                                        existing_reference=self.existing_reference)
        elif self.corridor_state == self.INSIDE_CORRIDOR and self.previous_corridor_state == self.OUTSIDE_CORRIDOR:
            # Do not print entering corridor if you are in the special case where we are cleaning up missed gates (indicated by apply maximum penalty)
            self.update_score(last_gate,
                              0,
                              "entering corridor",
                              position.latitude, position.longitude,
                              "information", f"entering_corridor")
            self.corridor_grace_time = self.scorecard.get_corridor_grace_time(self.contestant)

    def check_outside_corridor(self, track: List["Position"], last_gate: "Gate"):
        self.previous_corridor_state = self.corridor_state
        position = track[-1]
        if not self._check_inside_polygon(position.latitude, position.longitude):
            # We are outside the corridor
            if self.corridor_state == self.INSIDE_CORRIDOR:
                logger.info(
                    "{} {}: Heading outside of corridor".format(self.contestant, position.time))

                self.crossed_outside_position = position
                self.corridor_state = self.OUTSIDE_CORRIDOR
                self.crossed_outside_time = position.time
                self.crossed_outside_gate = last_gate
            self.check_and_apply_outside_penalty(position, last_gate)
        elif self.corridor_state == self.OUTSIDE_CORRIDOR:
            self.existing_reference = None
            logger.info(
                "{} {}: Back inside the corridor".format(self.contestant, position.time))
            self.corridor_state = self.INSIDE_CORRIDOR
            self.check_and_apply_outside_penalty(position, last_gate)
        self.previous_last_gate = last_gate
