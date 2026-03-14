import datetime
from multiprocessing import Queue

import matplotlib.pyplot as plt
import logging
from typing import List, Optional, Tuple, Dict
import numpy as np
from shapely.geometry import Polygon, Point

from display.calculators.calculator import (
    Calculator,
    OrchestratorState,
    OrchestratorEvent,
    FinishLinePassedEvent,
    GateMissedEvent,
    GatePassedEvent,
    AdaptiveStartEvent,
)
from display.calculators.calculator_utilities import PolygonHelper, get_shortest_intersection_time
from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route, INFORMATION, ANOMALY
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.utilities.gate_definitions import SECRETPOINT
from display.utilities.navigation_task_type_definitions import ANR_CORRIDOR

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
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
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
        route: "Route",
        score_processing_queue: Queue,
        live_processing: bool = True,
        projector=None,
    ):
        super().__init__(
            contestant,
            scorecard,
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
        self.last_visible_gate_missed_position = None
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

        # Consolidate per-leg penalties into a single excursion message
        self.excursion_accumulated_score = 0.0
        self.excursion_total_outside_seconds = 0.0
        self.excursion_any_leg_capped = False
        self.excursion_leg_details = []

        # Persistent leg tracking across multiple excursions
        self.leg_penalties = {}  # gate_name -> current total capped penalty for this leg
        self.leg_seconds = {}  # gate_name -> current total seconds outside for this leg

    def _is_gate_visible(self, gate: Gate) -> bool:
        """
        A gate is visible if it's not a secret point, OR if it's secret but has no time/gate checks.
        """
        if gate.type != SECRETPOINT:
            return True
        # Secret gate: only visible if BOTH checks are disabled
        return not gate.gate_check and not gate.time_check

    def _should_transition_leg(self, gate: Gate) -> bool:
        """
        Determines if a gate crossing should start a new scoring leg.
        - For ANR: Every gate is a leg boundary (usually turns).
        - For others: Only standard waypoints (non-secret) are boundaries.
        """
        if self.scorecard.calculator == ANR_CORRIDOR:
            return True
        return gate.type != SECRETPOINT

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]) -> Tuple[float, float]:
        """
        Danger level ranges from 0 to 100 where 100 is outside the corridor, and all other numbers represent half seconds
        """
        if not self.enroute:
            return 0, 0
        LOOKAHEAD_SECONDS = 30
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            # Live score should show total excursion penalty so far
            current_leg_incremental, _, _ = self._calculate_current_leg_penalty(
                datetime.datetime.now(datetime.timezone.utc) if self.live_processing else track[-1].time
            )

            return 100, self.excursion_accumulated_score + current_leg_incremental

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
        # GeoJSON is [lng, lat], our corridor_polygon list items are {"lat":..., "lng":...}
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
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        if not self.enroute:
            self.enroute = True
        self.check_outside_corridor(track, state.last_visible_gate)
        return []

    def on_gate_missed(self, event: GateMissedEvent):
        # Detect gate crossing while outside to advance/finalize leg
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            # Determine time and current leg status
            current_time = event.event_time or event.position.time
            leg_incremental, _, capped = self._calculate_current_leg_penalty(current_time)
            cap_str = " (capped)" if capped else ""

            # 1. Informational logging
            # Include detailed messages for visible gates (non-secret, or secret with no checks)
            if self._is_gate_visible(event.gate):
                self.update_score(
                    UpdateScoreMessage(
                        current_time,
                        event.gate,
                        0,
                        f"missed {event.gate.name} while outside corridor. Excursion penalty so far: {self.excursion_accumulated_score + leg_incremental}{cap_str}",
                        event.position.latitude,
                        event.position.longitude,
                        INFORMATION,
                        self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                    )
                )

            # 2. Leg transition (Scoring boundary)
            if self.corridor_maximum_penalty_is_per_leg:
                # Per the design: only visible/non-secret gates trigger a scoring leg transition
                if not self._should_transition_leg(event.gate):
                    return

                logger.info(
                    f"{self.contestant}: Finalizing scoring leg {self.crossed_outside_gate} because {event.gate} was missed."
                )

                # Re-calculate finalized values for transition
                leg_incremental, leg_seconds, is_capped = self._calculate_current_leg_penalty(current_time)

                # Update persistent leg totals
                last_leg = self.crossed_outside_gate
                gate_name = last_leg.name if last_leg else "Unknown"
                self.leg_penalties[gate_name] = self.leg_penalties.get(gate_name, 0.0) + leg_incremental
                self.leg_seconds[gate_name] = self.leg_seconds.get(gate_name, 0.0) + leg_seconds

                # Update excursion totals
                self.excursion_accumulated_score += leg_incremental
                self.excursion_total_outside_seconds += leg_seconds
                if is_capped:
                    self.excursion_any_leg_capped = True

                # Record details for the final consolidated message
                display_name = gate_name if (last_leg and self._is_gate_visible(last_leg)) else "Secret"
                self.excursion_leg_details.append(f"{display_name}: {leg_incremental}{cap_str}")

                if not self.has_passed_finish_point and event.gate.type != "fp":
                    # Restart penalty tracking for the new segment internally.
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                    self.current_leg_outside_start_time = current_time
                    self.is_first_leg_of_excursion = False
                    self.crossed_outside_gate = event.gate
                    self.accumulated_score = 0
            else:
                self.crossed_outside_gate = event.gate

    def on_gate_passed(self, event: "GatePassedEvent"):
        # Detect gate crossing while outside to advance/finalize leg
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            # Determine time and current leg status
            current_time = event.intersection_time
            leg_incremental, _, capped = self._calculate_current_leg_penalty(current_time)
            cap_str = " (capped)" if capped else ""

            # 1. Informational logging
            if self._is_gate_visible(event.gate):
                self.update_score(
                    UpdateScoreMessage(
                        current_time,
                        event.gate,
                        0,
                        f"passed {event.gate.name} while outside corridor. Excursion penalty so far: {self.excursion_accumulated_score + leg_incremental}{cap_str}",
                        event.position.latitude,
                        event.position.longitude,
                        INFORMATION,
                        self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                    )
                )

            # 2. Leg transition (Scoring boundary)
            if self.corridor_maximum_penalty_is_per_leg:
                # Per the design: only visible/non-secret gates trigger a scoring leg transition
                if not self._should_transition_leg(event.gate):
                    return

                logger.info(
                    f"{self.contestant}: Finalizing scoring leg {self.crossed_outside_gate} because {event.gate} was passed"
                )

                # Re-calculate finalized values for transition
                leg_incremental, leg_seconds, is_capped = self._calculate_current_leg_penalty(current_time)

                # Update persistent leg totals
                last_leg = self.crossed_outside_gate
                gate_name = last_leg.name if last_leg else "Unknown"
                self.leg_penalties[gate_name] = self.leg_penalties.get(gate_name, 0.0) + leg_incremental
                self.leg_seconds[gate_name] = self.leg_seconds.get(gate_name, 0.0) + leg_seconds

                # Update excursion totals
                self.excursion_accumulated_score += leg_incremental
                self.excursion_total_outside_seconds += leg_seconds
                if is_capped:
                    self.excursion_any_leg_capped = True

                # Record details for the final consolidated message
                display_name = gate_name if (last_leg and self._is_gate_visible(last_leg)) else "Secret"
                leg_cap_str = " (capped)" if is_capped else ""
                self.excursion_leg_details.append(f"{display_name}: {leg_incremental}{leg_cap_str}")

                if not self.has_passed_finish_point and event.gate.type != "fp":
                    # Restart penalty tracking for the new leg internally.
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                    self.current_leg_outside_start_time = current_time
                    self.is_first_leg_of_excursion = False
                    self.crossed_outside_gate = event.gate
                    self.accumulated_score = 0
            else:
                self.crossed_outside_gate = event.gate

    def _calculate_current_leg_penalty(self, current_time: datetime.datetime) -> Tuple[float, float, bool]:
        """
        Calculates the penalty and outside time for the current leg up to current_time.
        Returns (incremental_penalty, outside_seconds, is_capped)
        """
        start_time_ref = self.current_leg_outside_start_time or self.crossed_outside_time
        if start_time_ref is None:
            return 0.0, 0.0, False

        outside_time_this_segment = (current_time - start_time_ref).total_seconds()
        if outside_time_this_segment < 0:
            outside_time_this_segment = 0

        if self.is_first_leg_of_excursion:
            penalty_time = np.round(max(0.0, outside_time_this_segment - self.corridor_grace_time))
        else:
            # No grace time for subsequent legs of the same excursion
            penalty_time = np.round(outside_time_this_segment)

        raw_penalty = self.scorecard.corridor_outside_penalty * penalty_time
        capped = False

        if self.corridor_maximum_penalty_is_per_leg:
            gate_name = self.crossed_outside_gate.name if self.crossed_outside_gate else "Unknown"
            already_paid = self.leg_penalties.get(gate_name, 0.0)

            if self.scorecard.corridor_maximum_penalty > 0:
                headroom = max(0.0, self.scorecard.corridor_maximum_penalty - already_paid)
                if raw_penalty >= headroom:
                    raw_penalty = headroom
                    capped = True

        return float(raw_penalty), outside_time_this_segment, capped

    def check_and_apply_outside_penalty(
        self,
        position: ContestantReceivedPosition,
        last_visible_gate: Gate,
        current_time: Optional[datetime.datetime] = None,
    ):
        if self.crossed_outside_time is None:
            return

        # Use last_visible_gate for scoring attribution
        scoring_gate = last_visible_gate
        if scoring_gate is None:
            # Fallback to first non-dummy waypoint
            waypoints = self.route.waypoints
            if waypoints:
                scoring_gate = next((w for w in waypoints if w.type != "dummy"), waypoints[0])

        gate_name = scoring_gate.name if scoring_gate else "Unknown"

        # For consolidated reports, we use the base score type
        score_type = self.OUTSIDE_CORRIDOR_PENALTY_TYPE

        # Determine calculation time
        if current_time is None:
            if self.corridor_state == self.INSIDE_CORRIDOR:
                current_time = position.time - datetime.timedelta(seconds=1)
            else:
                current_time = position.time

        # Prevent double-logging or overlapping updates for the same position/event
        # BUT always allow if we are transitioning state to ensure finalization is logged
        is_transition = self.corridor_state != self.previous_corridor_state
        if self.last_finalized_time == (current_time, score_type) and not is_transition:
            return
        self.last_finalized_time = (current_time, score_type)

        # Calculate current leg's contribution live
        leg_incremental, leg_seconds, is_capped = self._calculate_current_leg_penalty(current_time)
        self.accumulated_score = leg_incremental

        entry_lat = self.crossed_outside_position[0] if self.crossed_outside_position else position.latitude
        entry_lon = self.crossed_outside_position[1] if self.crossed_outside_position else position.longitude

        # Transition handling
        if self.corridor_state == self.OUTSIDE_CORRIDOR and self.previous_corridor_state == self.INSIDE_CORRIDOR:
            # Emit "exiting corridor" message ONLY at the start of an excursion.
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
        elif self.corridor_state == self.INSIDE_CORRIDOR and self.previous_corridor_state == self.OUTSIDE_CORRIDOR:
            # Update persistent totals for the final leg of the excursion
            gate_id = last_visible_gate.name if last_visible_gate else "Unknown"
            self.leg_penalties[gate_id] = self.leg_penalties.get(gate_id, 0.0) + leg_incremental
            self.leg_seconds[gate_id] = self.leg_seconds.get(gate_id, 0.0) + leg_seconds

            # Consolidate and emit the final excursion penalty
            final_score = self.excursion_accumulated_score + leg_incremental
            final_time = self.excursion_total_outside_seconds + leg_seconds

            any_capped = self.excursion_any_leg_capped or is_capped
            cap_str = " (capped)" if any_capped else ""

            # Construct the detailed list of leg scores for this excursion
            leg_cap_str = " (capped)" if is_capped else ""
            display_name = gate_id if self._is_gate_visible(last_visible_gate or scoring_gate) else "Secret"
            all_leg_details = self.excursion_leg_details + [f"{display_name}: {leg_incremental}{leg_cap_str}"]
            leg_scores_list_str = ", ".join(all_leg_details)

            message = "outside corridor ({} s)".format(int(np.round(final_time)))
            if self.corridor_maximum_penalty_is_per_leg:
                message += f". Leg scores: [{leg_scores_list_str}]. Total: {final_score}{cap_str}"
            elif any_capped:
                message += cap_str

            self.update_score(
                UpdateScoreMessage(
                    current_time,
                    scoring_gate,
                    final_score,
                    message,
                    position.latitude,
                    position.longitude,
                    ANOMALY,
                    score_type,
                    # We don't provide maximum_score here because we already applied per-leg caps internally
                    # and if per-leg is off, accumulated_score already handles the global cap.
                    maximum_score=(
                        None if self.corridor_maximum_penalty_is_per_leg else self.scorecard.corridor_maximum_penalty
                    ),
                )
            )
            # Reset excursion state
            self.accumulated_score = 0
            self.excursion_accumulated_score = 0
            self.excursion_total_outside_seconds = 0
            self.excursion_any_leg_capped = False
            self.excursion_leg_details = []

    def finalise(self, track: List[ContestantReceivedPosition]):
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            position = track[-1] if track else None
            if position:
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
                self.check_and_apply_outside_penalty(position, self.crossed_outside_gate or self.previous_last_gate)

    def check_outside_corridor(self, track: List[ContestantReceivedPosition], last_visible_gate: "Gate"):
        if self.has_passed_finish_point:
            return

        self.previous_corridor_state = self.corridor_state
        position = track[-1]
        is_inside = self._check_inside_polygon(position)

        if not is_inside:
            if self.corridor_state == self.INSIDE_CORRIDOR:
                logger.info("{} {}: Heading outside of corridor".format(self.contestant, position.time))
                self.crossed_outside_position = (position.latitude, position.longitude)
                self.corridor_state = self.OUTSIDE_CORRIDOR
                self.crossed_outside_time = position.time
                self.crossed_outside_gate = last_visible_gate
                self.current_leg_outside_start_time = position.time
                self.is_first_leg_of_excursion = True

                # Start of a new excursion
                self.excursion_accumulated_score = 0.0
                self.excursion_total_outside_seconds = 0.0
                self.excursion_any_leg_capped = False
                self.excursion_leg_details = []
            self.check_and_apply_outside_penalty(position, last_visible_gate)
        elif self.corridor_state == self.OUTSIDE_CORRIDOR:
            logger.info("{} {}: Back inside the corridor".format(self.contestant, position.time))
            self.corridor_state = self.INSIDE_CORRIDOR
            self.check_and_apply_outside_penalty(position, last_visible_gate)

            # Reset state for next excursion
            self.crossed_outside_position = None
            self.crossed_outside_time = None
            self.current_leg_outside_start_time = None
            self.is_first_leg_of_excursion = True

        self.previous_last_gate = last_visible_gate

    def on_adaptive_start(self, event: AdaptiveStartEvent):
        pass
