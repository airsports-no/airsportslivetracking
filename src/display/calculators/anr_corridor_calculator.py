import datetime
from multiprocessing import Queue

import matplotlib.pyplot as plt
import logging
from typing import List, Optional, Tuple
import numpy as np
from shapely.geometry import Polygon, Point

from display.calculators.calculator import (
    Calculator,
    GatekeeperState,
    GatekeeperEvent,
    FinishLinePassedEvent,
    GateMissedEvent,
    GatePassedEvent,
)
from display.calculators.calculator_utilities import PolygonHelper, get_shortest_intersection_time
from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route, INFORMATION, ANOMALY
from display.models.contestant_utility_models import ContestantReceivedPosition

logger = logging.getLogger(__name__)


class AnrCorridorCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        if not self.has_passed_finish_point:
            self.has_passed_finish_point = True
            if self.corridor_state == self.OUTSIDE_CORRIDOR:
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
                # Finalize penalty at the crossing time
                self.check_and_apply_outside_penalty(
                    event.position, self.crossed_outside_gate or event.last_gate, current_time=event.event_time
                )

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        self.enroute = False
        self.accumulated_score = 0
        return []

    INSIDE_CORRIDOR = 0
    OUTSIDE_CORRIDOR = 1
    OUTSIDE_CORRIDOR_PENALTY_TYPE = "outside_corridor"

    def __init__(
        self,
        contestant: "Contestant",
        scorecard: "Scorecard",
        gates: List["Gate"],
        route: "Route",
        score_processing_queue: Queue,
        live_processing: bool = True,
        projector=None,
    ):
        super().__init__(
            contestant,
            scorecard,
            gates,
            route,
            score_processing_queue,
            live_processing=live_processing,
            projector=projector,
        )
        self.corridor_state = self.INSIDE_CORRIDOR
        self.previous_corridor_state = self.INSIDE_CORRIDOR
        self.crossed_outside_time = None
        self.has_passed_finish_point = False
        self.last_outside_penalty = None
        self.last_gate_missed_position = None
        self.previous_last_gate = None
        self.crossed_outside_position = None
        self.crossed_outside_gate = None
        self.enroute = False
        self.corridor_grace_time = self.scorecard.corridor_grace_time
        self.corridor_maximum_penalty_is_per_leg = self.scorecard.corridor_maximum_penalty_is_per_leg
        self.current_leg_outside_start_time = None
        self.is_first_leg_of_excursion = True
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude)
        self._bounds_cache = {}
        self.track_polygon = self.build_polygon()
        self.existing_reference = None
        self.accumulated_score = 0
        self.previous_existing_reference = None
        self.last_finalized_time = None

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]) -> Tuple[float, float]:
        """
        Danger level ranges from 0 to 100 where 100 is outside the corridor, and all other numbers represent half seconds
        """
        if not self.enroute:
            return 0, 0
        LOOKAHEAD_SECONDS = 30
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            return 100, self.accumulated_score
        distance_danger = 0
        shortest_time = get_shortest_intersection_time(
            track, self.polygon_helper, [("test", self.track_polygon)], LOOKAHEAD_SECONDS, from_inside=True
        )
        lookahead_danger = 99 * (LOOKAHEAD_SECONDS - shortest_time) / LOOKAHEAD_SECONDS
        if len(track) > 0:
            position = track[-1]
            MAXIMUM_DISTANCE = 1852  # m

            # Fast distance check using projected coordinates if available
            p_x = getattr(position, "projected_x", None)
            p_y = getattr(position, "projected_y", None)

            if p_x is not None and self.projector:
                # We can't easily use track_polygon if it's UTM while position is AEQD
                # So we fallback to standard check for now until we unify projections
                polygon_distance = min(
                    [MAXIMUM_DISTANCE, self._distance_from_point_to_polygons(position.latitude, position.longitude)]
                )
            else:
                polygon_distance = min(
                    [MAXIMUM_DISTANCE, self._distance_from_point_to_polygons(position.latitude, position.longitude)]
                )

            distance_danger = 30 * (MAXIMUM_DISTANCE - polygon_distance) / MAXIMUM_DISTANCE
        return max([lookahead_danger, distance_danger]), self.accumulated_score

    def build_polygon(self):
        points = [(item["lat"], item["lng"]) for item in self.contestant.navigation_task.route.corridor_polygon]
        points = np.array(points)

        if self.projector:
            # Use AEQD projection for the polygon to match position.projected_x/y
            transformed_points = []
            for lat, lon in points:
                p = self.projector.project_point(lat, lon)
                transformed_points.append((p.projected_x, p.projected_y))
            return Polygon(transformed_points)
        else:
            transformed_points = self.polygon_helper.utm.transform_points(
                self.polygon_helper.pc, points[:, 1], points[:, 0]
            )
            return Polygon(transformed_points)

    def plot_polygon(self):
        # imagery = OSM()
        ax = plt.axes(projection=self.polygon_helper.utm)
        # ax.add_image(imagery, 8)
        ax.set_aspect("auto")
        ax.plot(self.track_polygon.boundary.xy[0], self.track_polygon.boundary.xy[1])
        ax.add_geometries([self.track_polygon], crs=self.polygon_helper.utm, facecolor="blue", alpha=0.4)
        plt.savefig("polygon.png", dpi=100)

    def _check_inside_polygon(self, position: ContestantReceivedPosition) -> bool:
        """
        Returns true if the point lies inside the corridor
        """
        p_x = getattr(position, "projected_x", None)
        p_y = getattr(position, "projected_y", None)

        if p_x is not None and self.projector:
            # Use pre-projected coordinates directly!
            x, y = p_x, p_y
        else:
            # Fallback to UTM projection
            x, y = self.polygon_helper.utm.transform_point(
                position.longitude, position.latitude, self.polygon_helper.pc
            )

        # Direct bounding box check
        if self.track_polygon not in self._bounds_cache:
            self._bounds_cache[self.track_polygon] = self.track_polygon.bounds

        minx, miny, maxx, maxy = self._bounds_cache[self.track_polygon]
        if not (minx <= x <= maxx and miny <= y <= maxy):
            return False

        # Still need contains() for precise check
        p = Point(x, y)
        return self.track_polygon.contains(p)

    def _distance_from_point_to_polygons(self, latitude: float, longitude: float) -> float:
        """
        :return: Distance to inside or outside the polygon (metres)
        """
        return self.polygon_helper.distance_from_point_to_polygons([("test", self.track_polygon)], latitude, longitude)[
            "test"
        ]

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        self.enroute = True
        self.check_outside_corridor(track, state.last_gate)
        return []

    def on_gate_missed(self, event: GateMissedEvent):
        # Detect gate crossing while outside to advance/finalize leg
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            logger.info(
                f"{self.contestant}: Finalizing leg {self.crossed_outside_gate} because {event.gate} was missed"
            )
            if self.corridor_maximum_penalty_is_per_leg:
                # Finalize penalty for the leg we just left
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
                # We use event.event_time or event.position.time as the end of the previous leg
                self.check_and_apply_outside_penalty(event.position, self.crossed_outside_gate, current_time=event.event_time)

                if not self.has_passed_finish_point and event.gate.type != "fp":
                    # Restart penalty for the new leg
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.INSIDE_CORRIDOR
                    self.current_leg_outside_start_time = event.event_time or event.position.time
                    self.is_first_leg_of_excursion = False
                    self.crossed_outside_gate = event.gate
                    self.check_and_apply_outside_penalty(event.position, event.gate, current_time=event.event_time)
            else:
                self.crossed_outside_gate = event.gate

    def on_gate_passed(self, event: "GatePassedEvent"):
        # Detect gate crossing while outside to advance/finalize leg
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            logger.info(
                f"{self.contestant}: Finalizing leg {self.crossed_outside_gate} because {event.gate} was passed"
            )
            if self.corridor_maximum_penalty_is_per_leg:
                # Finalize penalty for the leg we just left
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
                # We use event.intersection_time as the end of the previous leg
                self.check_and_apply_outside_penalty(event.position, self.crossed_outside_gate, current_time=event.intersection_time)

                if not self.has_passed_finish_point and event.gate.type != "fp":
                    # Restart penalty for the new leg
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.INSIDE_CORRIDOR
                    self.current_leg_outside_start_time = event.intersection_time
                    self.is_first_leg_of_excursion = False
                    self.crossed_outside_gate = event.gate
                    self.check_and_apply_outside_penalty(event.position, event.gate, current_time=event.intersection_time)
            else:
                self.crossed_outside_gate = event.gate

    def check_and_apply_outside_penalty(
        self,
        position: ContestantReceivedPosition,
        last_gate: Gate,
        current_time: Optional[datetime.datetime] = None,
    ):
        if self.crossed_outside_time is None:
            return

        # Determine calculation time
        if current_time is None:
            if self.corridor_state == self.INSIDE_CORRIDOR:
                current_time = position.time - datetime.timedelta(seconds=1)
            else:
                current_time = position.time

        # Use first waypoint as a fallback if last_gate is None
        scoring_gate = self.get_last_non_secret_gate(last_gate) if last_gate else self.gates[0]
        gate_name = last_gate.name if last_gate else scoring_gate.name

        score_type = self.OUTSIDE_CORRIDOR_PENALTY_TYPE
        if self.corridor_maximum_penalty_is_per_leg:
            score_type = f"{self.OUTSIDE_CORRIDOR_PENALTY_TYPE}_{gate_name}"

        # Prevent double-logging or overlapping updates for the same position/event
        if self.last_finalized_time == (current_time, score_type):
            return

        if self.corridor_maximum_penalty_is_per_leg:
            outside_time_this_leg = (
                current_time - (self.current_leg_outside_start_time or self.crossed_outside_time)
            ).total_seconds()
            if self.is_first_leg_of_excursion:
                penalty_time = np.round(max(0.0, outside_time_this_leg - self.corridor_grace_time))
            else:
                # No grace time for subsequent legs of the same excursion
                penalty_time = np.round(outside_time_this_leg)
            outside_time_for_message = outside_time_this_leg
        else:
            outside_time_total = (current_time - self.crossed_outside_time).total_seconds()
            penalty_time = np.round(max(0.0, outside_time_total - self.corridor_grace_time))
            outside_time_for_message = outside_time_total

        self.accumulated_score = self.scorecard.corridor_outside_penalty * penalty_time if penalty_time > 0 else 0

        entry_lat = self.crossed_outside_position.latitude if self.crossed_outside_position else position.latitude
        entry_lon = self.crossed_outside_position.longitude if self.crossed_outside_position else position.longitude

        # Transition handling
        if self.corridor_state == self.OUTSIDE_CORRIDOR and self.previous_corridor_state == self.INSIDE_CORRIDOR:
            self.update_score(
                UpdateScoreMessage(
                    position.time,
                    scoring_gate,
                    0,
                    "exiting corridor",
                    entry_lat,
                    entry_lon,
                    INFORMATION,
                    score_type,
                )
            )
            self.last_finalized_time = (current_time, score_type)
        elif self.corridor_state == self.INSIDE_CORRIDOR and self.previous_corridor_state == self.OUTSIDE_CORRIDOR:
            self.update_score(
                UpdateScoreMessage(
                    current_time,
                    scoring_gate,
                    self.accumulated_score,
                    "outside corridor ({} s)".format(int(outside_time_for_message)),
                    position.latitude,
                    position.longitude,
                    ANOMALY,
                    score_type,
                    maximum_score=self.scorecard.corridor_maximum_penalty,
                )
            )
            self.accumulated_score = 0
            self.last_finalized_time = (current_time, score_type)

    def finalise(self, track: List[ContestantReceivedPosition]):
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            position = track[-1] if track else None
            if position:
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
                self.check_and_apply_outside_penalty(position, self.crossed_outside_gate or self.previous_last_gate)

    def check_outside_corridor(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        if self.has_passed_finish_point:
            return
        
        self.previous_corridor_state = self.corridor_state
        position = track[-1]
        is_inside = self._check_inside_polygon(position)

        if not is_inside:
            if self.corridor_state == self.INSIDE_CORRIDOR:
                logger.info("{} {}: Heading outside of corridor".format(self.contestant, position.time))
                self.crossed_outside_position = position
                self.corridor_state = self.OUTSIDE_CORRIDOR
                self.crossed_outside_time = position.time
                self.crossed_outside_gate = last_gate
                self.current_leg_outside_start_time = position.time
                self.is_first_leg_of_excursion = True
            self.check_and_apply_outside_penalty(position, last_gate)
        elif self.corridor_state == self.OUTSIDE_CORRIDOR:
            logger.info("{} {}: Back inside the corridor".format(self.contestant, position.time))
            self.corridor_state = self.INSIDE_CORRIDOR
            self.check_and_apply_outside_penalty(position, last_gate)
            
            # Reset state for next excursion
            self.crossed_outside_position = None
            self.crossed_outside_time = None
            self.current_leg_outside_start_time = None
            self.is_first_leg_of_excursion = True

        self.previous_last_gate = last_gate
