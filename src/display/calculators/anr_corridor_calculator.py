import logging
from typing import TYPE_CHECKING
import numpy as np
from shapely.geometry import Polygon, Point

import cartopy.crs as ccrs
from display.calculators.calculator_utilities import cross_track_gate
from display.calculators.precision_calculator import PrecisionCalculator
from display.models import Contestant

if TYPE_CHECKING:
    from influx_facade import InfluxFacade

logger = logging.getLogger(__name__)


class AnrCorridorCalculator(PrecisionCalculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """
    INSIDE_CORRIDOR = 0
    OUTSIDE_CORRIDOR = 1
    OUTSIDE_CORRIDOR_PENALTY_TYPE = "outside_corridor"

    def __init__(self, contestant: "Contestant", influx: "InfluxFacade", live_processing: bool = True):
        super().__init__(contestant, influx, live_processing)
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
            # latitude, longitude, so reverse
            points.append(list(reversed(waypoint.gate_line[0])))
        for waypoint in reversed(self.contestant.navigation_task.route.waypoints):
            points.append(list(reversed(waypoint.gate_line[1])))
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

    def calculate_score(self):
        super().calculate_score()
        self.check_outside_corridor()

    def check_outside_corridor(self):
        if self.tracking_state == self.FINISHED:
            return
        if self.last_gate and len(self.outstanding_gates) > 0:
            # We are inside the corridor, between starting point and finish point
            if not self._check_inside_polygon(self.track[-1].latitude, self.track[-1].longitude):
                # We are outside the corridor
                if self.corridor_state == self.INSIDE_CORRIDOR:
                    logger.info(
                        "{} {}: Heading outside of corridor".format(self.contestant, self.track[-1].time))

                    self.crossed_outside_position = self.track[-1]
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.crossed_outside_time = self.track[-1].time
            elif self.corridor_state == self.OUTSIDE_CORRIDOR:
                self.corridor_state = self.INSIDE_CORRIDOR
                outside_time = (self.track[-1].time - self.crossed_outside_time).total_seconds()
                penalty_time = outside_time - self.scorecard.get_corridor_grace_time(self.contestant)
                logger.info(
                    "{} {}: Back inside the corridor after {} seconds".format(self.contestant, self.track[-1].time,
                                                                              outside_time))
                if penalty_time > 0:
                    penalty_time = np.round(penalty_time)
                    self.update_score(self.last_gate,
                                      self.scorecard.get_corridor_outside_penalty(self.contestant) * penalty_time,
                                      "outside corridor ({} seconds)".format(int(penalty_time)),
                                      self.crossed_outside_position.latitude, self.crossed_outside_position.longitude,
                                      "anomaly", self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                                      maximum_score=self.scorecard.get_corridor_outside_maximum_penalty(
                                          self.contestant))
