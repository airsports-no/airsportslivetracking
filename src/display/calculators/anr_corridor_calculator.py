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
        
        self.polygon_helper = PolygonHelper(self.projector)
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

            p_x = getattr(position, "projected_x", None)
            p_y = getattr(position, "projected_y", None)
            
            if p_x is None or p_y is None:
                raise ValueError(f"Position at {position.time} is missing projected coordinates")

            p = Point(p_x, p_y)
            polygon_distance = self.track_polygon.exterior.distance(p)
            polygon_distance = min(MAXIMUM_DISTANCE, polygon_distance)

            distance_danger = 30 * (MAXIMUM_DISTANCE - polygon_distance) / MAXIMUM_DISTANCE
        return max([lookahead_danger, distance_danger]), self.accumulated_score

    def build_polygon(self):
        points = [(item["lat"], item["lng"]) for item in self.contestant.navigation_task.route.corridor_polygon]
        # GeoJSON is [lng, lat], our corridor_polygon list items are {"lat":..., "lng":...}
        # PolygonHelper.build_polygon expects list of [lng, lat]
        path = [[item["lng"], item["lat"]] for item in self.contestant.navigation_task.route.corridor_polygon]
        return self.polygon_helper.build_polygon(path)

    def plot_polygon(self):
        fig, ax = plt.subplots()
        ax.set_aspect("equal")
        ax.plot(*self.track_polygon.exterior.xy)
        plt.savefig("polygon.png", dpi=100)

    def _check_inside_polygon(self, position: ContestantReceivedPosition) -> bool:
        """
        Returns true if the point lies inside the corridor
        """
        x = getattr(position, "projected_x", None)
        y = getattr(position, "projected_y", None)

        if x is None or y is None:
            raise ValueError(f"Position at {position.time} is missing projected coordinates")

        # Direct bounding box check
        if self.track_polygon not in self._bounds_cache:
            self._bounds_cache[self.track_polygon] = self.track_polygon.bounds

        minx, miny, maxx, maxy = self._bounds_cache[self.track_polygon]
        if not (minx <= x <= maxx and miny <= y <= maxy):
            return False

        # Still need contains() for precise check
        p = Point(x, y)
        return self.track_polygon.contains(p)

    def _distance_from_point_to_polygons(self, position: ContestantReceivedPosition) -> float:
        """
        :return: Distance to inside or outside the polygon (metres)
        """
        p_x = getattr(position, "projected_x", None)
        p_y = getattr(position, "projected_y", None)
        if p_x is None or p_y is None:
            raise ValueError(f"Position at {position.time} is missing projected coordinates")

        return self.polygon_helper.distance_from_point_to_polygons(
            [("test", self.track_polygon)], position.latitude, position.longitude, p_x, p_y
        )["test"]

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        self.enroute = state.enroute
        if state.enroute:
            self.check_outside_corridor(track, state.last_gate)
        return []

    def on_gate_missed(self, event: GateMissedEvent):
        # Detect gate crossing while outside to advance/finalize leg
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            logger.info(
                f"{self.contestant}: Finalizing leg {self.crossed_outside_gate} because {event.gate} was missed. Max per leg: {self.corridor_maximum_penalty_is_per_leg}"
            )
            if self.corridor_maximum_penalty_is_per_leg:
                # Finalize penalty for the leg we just left
                self._finalize_current_leg_penalty(
                    event.position, self.crossed_outside_gate, event.event_time or event.position.time
                )

                if not self.has_passed_finish_point and event.gate.type != "fp":
                    # Restart penalty for the new leg.
                    # Setting previous_corridor_state to OUTSIDE_CORRIDOR prevents a redundant "exiting corridor" message.
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                    self.current_leg_outside_start_time = event.event_time or event.position.time
                    self.is_first_leg_of_excursion = False
                    self.crossed_outside_gate = event.gate
                    # Initial check for the new leg
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
                self._finalize_current_leg_penalty(event.position, self.crossed_outside_gate, event.intersection_time)

                if not self.has_passed_finish_point and event.gate.type != "fp":
                    # Restart penalty for the new leg.
                    # Setting previous_corridor_state to OUTSIDE_CORRIDOR prevents a redundant "exiting corridor" message.
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                    self.current_leg_outside_start_time = event.intersection_time
                    self.is_first_leg_of_excursion = False
                    self.crossed_outside_gate = event.gate
                    # Initial check for the new leg
                    self.check_and_apply_outside_penalty(
                        event.position, event.gate, current_time=event.intersection_time
                    )
            else:
                self.crossed_outside_gate = event.gate

    def _finalize_current_leg_penalty(
        self, position: ContestantReceivedPosition, gate: Gate, current_time: datetime.datetime
    ):
        """
        Forcefully finalize the current leg penalty and log it, as if we just came inside.
        Used during leg transitions while remaining outside.
        """
        # Save states
        old_state = self.corridor_state
        old_prev = self.previous_corridor_state

        # Force transition state
        self.corridor_state = self.INSIDE_CORRIDOR
        self.previous_corridor_state = self.OUTSIDE_CORRIDOR

        self.check_and_apply_outside_penalty(position, gate, current_time=current_time)

        # Restore states
        self.corridor_state = old_state
        self.previous_corridor_state = old_prev

    def check_and_apply_outside_penalty(
        self,
        position: ContestantReceivedPosition,
        last_gate: Gate,
        current_time: Optional[datetime.datetime] = None,
    ):
        if self.crossed_outside_time is None:
            return

        # Use first waypoint as a fallback if last_gate is None
        scoring_gate = self.get_last_non_secret_gate(last_gate) if last_gate else self.gates[0]
        gate_name = last_gate.name if last_gate else scoring_gate.name

        score_type = self.OUTSIDE_CORRIDOR_PENALTY_TYPE
        if self.corridor_maximum_penalty_is_per_leg:
            score_type = f"{self.OUTSIDE_CORRIDOR_PENALTY_TYPE}_{gate_name}"

        # Determine calculation time
        if current_time is None:
            if self.corridor_state == self.INSIDE_CORRIDOR:
                current_time = position.time - datetime.timedelta(seconds=1)
            else:
                current_time = position.time

        # Ensure current_time is not before start time to prevent negative durations
        start_time_ref = self.current_leg_outside_start_time or self.crossed_outside_time
        if current_time < start_time_ref:
            current_time = start_time_ref

        # Prevent double-logging or overlapping updates for the same position/event
        # BUT always allow if we are transitioning state to ensure finalization is logged
        is_transition = self.corridor_state != self.previous_corridor_state
        if self.last_finalized_time == (position.time, score_type) and not is_transition:
            return
        self.last_finalized_time = (position.time, score_type)

        if self.corridor_maximum_penalty_is_per_leg:
            outside_time_this_leg = (current_time - start_time_ref).total_seconds()
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
            # We want to emit the "exiting corridor" message if:
            # 1. This is the first leg of the excursion (just headed out)
            # 2. We just changed to a new scoring gate while outside (informative transition)
            is_new_gate = getattr(self, "last_exiting_gate_name", None) != scoring_gate.name
            if self.is_first_leg_of_excursion or is_new_gate:
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
                self.last_exiting_gate_name = scoring_gate.name
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
