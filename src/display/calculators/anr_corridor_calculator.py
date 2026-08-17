import datetime
import logging
from multiprocessing import Queue

from typing import List, Optional, Tuple
import numpy as np
from shapely.geometry import Point, LineString

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
from display.utilities.cima_task_type_definitions import ANR_CATALOGUE

logger = logging.getLogger(__name__)


class AnrCorridorCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    INSIDE_CORRIDOR = 0
    OUTSIDE_CORRIDOR = 1
    OUTSIDE_CORRIDOR_PENALTY_TYPE = "outside_corridor"
    ROUTE_TO_SP_SCORE_TYPE = "anr_route_to_sp"
    ROUTE_FROM_FP_SCORE_TYPE = "anr_route_from_fp"

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

        self.polygon_helper = PolygonHelper(self.projector)
        self._bounds_cache = {}
        self.track_polygon = self.build_polygon()
        self.accumulated_score = 0
        self.last_finalized_time = None

        # Consolidate per-leg penalties into a single excursion message
        self.excursion_accumulated_score = 0.0
        self.excursion_total_outside_seconds = 0.0
        self.excursion_any_leg_capped = False
        self.excursion_leg_details = []

        # Persistent leg tracking across multiple excursions
        self.leg_penalties = {}
        self.leg_seconds = {}

        self.route_to_sp_polygon = self._build_auxiliary_polygon("route_to_sp_path")
        self.route_from_fp_polygon = self._build_auxiliary_polygon("route_from_fp_path")
        self.route_to_sp_scored = False
        self.route_from_fp_scored = False

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        if not self.has_passed_finish_point:
            self.has_passed_finish_point = True
            if self.corridor_state == self.OUTSIDE_CORRIDOR:
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
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
        self._check_auxiliary_route_compliance(track, before_start=not state.has_any_gate_passed, after_finish=state.has_passed_finishpoint)
        return []

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]) -> Tuple[float, float]:
        if not self.enroute:
            return 0, 0
        LOOKAHEAD_SECONDS = 30
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            current_leg_incremental, _, _ = self._calculate_current_leg_penalty(track[-1].time)
            return 100, self.excursion_accumulated_score + current_leg_incremental

        distance_danger = 0
        shortest_time = get_shortest_intersection_time(
            track, self.polygon_helper, [("test", self.track_polygon)], LOOKAHEAD_SECONDS, from_inside=True
        )
        lookahead_danger = 99 * (LOOKAHEAD_SECONDS - shortest_time) / LOOKAHEAD_SECONDS
        if len(track) > 0:
            position = track[-1]
            MAXIMUM_DISTANCE = 1852
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
        path = [[item["lng"], item["lat"]] for item in self.contestant.navigation_task.route.corridor_polygon]
        return self.polygon_helper.build_polygon(path)

    def _build_auxiliary_polygon(self, key: str):
        if getattr(self.contestant.navigation_task, "task_subtype", None) != ANR_CATALOGUE:
            return None
        payload = {}
        if hasattr(self.contestant, "contestanttaskconfiguration") and self.contestant.contestanttaskconfiguration.is_valid:
            payload = self.contestant.contestanttaskconfiguration.compiled_effective_route_payload or {}
        # Auxiliary route compliance intentionally consumes compiled contestant
        # payloads rather than re-reading editable_route directly, so scoring
        # follows the same compiled-task snapshot that maps and declarations use.
        compiled = payload.get("compiled_auxiliary_paths", {}).get(key, [])
        if not compiled:
            return None
        coordinates = compiled[0]
        if len(coordinates) < 2:
            return None
        # Reuse the ANR corridor width for auxiliary route compliance so the
        # pre-start/post-finish checks follow the same corridor semantics as
        # the main route body.
        half_width_m = float(self.route.corridor_width) * 1852 / 2
        projected = []
        for lon, lat in coordinates:
            p = self.projector.project_point(lat, lon)
            projected.append((p.projected_x, p.projected_y))
        line_string = LineString(projected)
        return line_string.buffer(half_width_m, cap_style=2, join_style=2)


    def _check_inside_polygon(self, position: ContestantReceivedPosition) -> bool:
        x = getattr(position, "projected_x", None)
        y = getattr(position, "projected_y", None)
        if x is None or y is None:
            raise ValueError(f"Position at {position.time} is missing projected coordinates")
        if self.track_polygon not in self._bounds_cache:
            self._bounds_cache[self.track_polygon] = self.track_polygon.bounds
        minx, miny, maxx, maxy = self._bounds_cache[self.track_polygon]
        if not (minx <= x <= maxx and miny <= y <= maxy):
            return False
        p = Point(x, y)
        return self.track_polygon.contains(p)

    def _distance_from_point_to_polygons(self, position: ContestantReceivedPosition) -> float:
        p_x = getattr(position, "projected_x", None)
        p_y = getattr(position, "projected_y", None)
        if p_x is None or p_y is None:
            raise ValueError(f"Position at {position.time} is missing projected coordinates")
        return self.polygon_helper.distance_from_point_to_polygons(
            [("test", self.track_polygon)], p_x, p_y
        )["test"]

    def _is_inside_auxiliary_polygon(self, position: ContestantReceivedPosition, polygon) -> bool:
        if polygon is None:
            return True
        x = getattr(position, "projected_x", None)
        y = getattr(position, "projected_y", None)
        if x is None or y is None:
            raise ValueError(f"Position at {position.time} is missing projected coordinates")
        return polygon.contains(Point(x, y))

    def _check_auxiliary_route_compliance(self, track: List[ContestantReceivedPosition], before_start: bool, after_finish: bool) -> None:
        if getattr(self.contestant.navigation_task, "task_subtype", None) != ANR_CATALOGUE or not track:
            return
        position = track[-1]
        # These penalties are one-shot phase checks: once the contestant leaves
        # the compiled auxiliary corridor before start or after finish, the
        # corresponding score entry is emitted exactly once.
        if before_start and not self.route_to_sp_scored and not self._is_inside_auxiliary_polygon(position, self.route_to_sp_polygon):
            self.route_to_sp_scored = True
            gate = self.route.first_takeoff_gate or self.route.waypoints[0]
            penalty = float(getattr(self.scorecard, "anr_route_to_sp_penalty", 200) or 200)
            self.update_score(
                UpdateScoreMessage(
                    position.time,
                    gate,
                    penalty,
                    "route to SP not followed",
                    float(position.latitude),
                    float(position.longitude),
                    ANOMALY,
                    self.ROUTE_TO_SP_SCORE_TYPE,
                )
            )
        if after_finish and not self.route_from_fp_scored and not self._is_inside_auxiliary_polygon(position, self.route_from_fp_polygon):
            self.route_from_fp_scored = True
            gate = self.route.first_landing_gate or self.route.waypoints[-1]
            penalty = float(getattr(self.scorecard, "anr_route_from_fp_penalty", 200) or 200)
            self.update_score(
                UpdateScoreMessage(
                    position.time,
                    gate,
                    penalty,
                    "route from FP not followed",
                    float(position.latitude),
                    float(position.longitude),
                    ANOMALY,
                    self.ROUTE_FROM_FP_SCORE_TYPE,
                )
            )

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
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            current_time = event.event_time or event.position.time
            leg_incremental, _, capped = self._calculate_current_leg_penalty(current_time)
            cap_str = " (capped)" if capped else ""
            if event.gate.is_visible:
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
            if self.corridor_maximum_penalty_is_per_leg:
                if not event.gate.is_visible:
                    return
                if event.gate.type == "fp":
                    # The finish gate doesn't start a new leg, and
                    # passed_finishpoint() (triggered immediately after this
                    # by the orchestrator) finalizes the whole excursion via
                    # check_and_apply_outside_penalty using this same,
                    # still-open leg boundary. Accumulating here too would
                    # double-count this segment's time and penalty.
                    return
                leg_incremental, leg_seconds, is_capped = self._calculate_current_leg_penalty(current_time)
                last_leg = self.crossed_outside_gate
                gate_name = last_leg.name if last_leg else "Unknown"
                self.leg_penalties[gate_name] = self.leg_penalties.get(gate_name, 0.0) + leg_incremental
                self.leg_seconds[gate_name] = self.leg_seconds.get(gate_name, 0.0) + leg_seconds
                self.excursion_accumulated_score += leg_incremental
                self.excursion_total_outside_seconds += leg_seconds
                if is_capped:
                    self.excursion_any_leg_capped = True
                display_name = gate_name if (last_leg and last_leg.is_visible) else "Secret"
                self.excursion_leg_details.append(f"{display_name}: {float(leg_incremental):.1f}{cap_str}")
                if not self.has_passed_finish_point:
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                    self.current_leg_outside_start_time = current_time
                    self.crossed_outside_gate = event.gate
                    self.accumulated_score = 0
            else:
                self.crossed_outside_gate = event.gate

    def on_gate_passed(self, event: "GatePassedEvent"):
        if self.corridor_state == self.OUTSIDE_CORRIDOR:
            current_time = event.intersection_time
            leg_incremental, _, capped = self._calculate_current_leg_penalty(current_time)
            cap_str = " (capped)" if capped else ""
            if event.gate.is_visible:
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
            if self.corridor_maximum_penalty_is_per_leg:
                if not event.gate.is_visible:
                    return
                if event.gate.type == "fp":
                    # See the matching comment in on_gate_missed: the finish
                    # gate doesn't start a new leg, and passed_finishpoint()
                    # (triggered immediately after this by the orchestrator)
                    # finalizes the whole excursion via
                    # check_and_apply_outside_penalty using this same,
                    # still-open leg boundary. Accumulating here too would
                    # double-count this segment's time and penalty.
                    return
                leg_incremental, leg_seconds, is_capped = self._calculate_current_leg_penalty(current_time)
                last_leg = self.crossed_outside_gate
                gate_name = last_leg.name if last_leg else "Unknown"
                self.leg_penalties[gate_name] = self.leg_penalties.get(gate_name, 0.0) + leg_incremental
                self.leg_seconds[gate_name] = self.leg_seconds.get(gate_name, 0.0) + leg_seconds
                self.excursion_accumulated_score += leg_incremental
                self.excursion_total_outside_seconds += leg_seconds
                if is_capped:
                    self.excursion_any_leg_capped = True
                display_name = gate_name if (last_leg and last_leg.is_visible) else "Secret"
                leg_cap_str = " (capped)" if is_capped else ""
                self.excursion_leg_details.append(f"{display_name}: {float(leg_incremental):.1f}{leg_cap_str}")
                if not self.has_passed_finish_point:
                    self.corridor_state = self.OUTSIDE_CORRIDOR
                    self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                    self.current_leg_outside_start_time = current_time
                    self.crossed_outside_gate = event.gate
                    self.accumulated_score = 0
            else:
                self.crossed_outside_gate = event.gate

    def _calculate_current_leg_penalty(self, current_time: datetime.datetime) -> Tuple[float, float, bool]:
        start_time_ref = self.current_leg_outside_start_time or self.crossed_outside_time
        if start_time_ref is None:
            return 0.0, 0.0, False
        outside_time_this_segment = (current_time - start_time_ref).total_seconds()
        if outside_time_this_segment < 0:
            outside_time_this_segment = 0

        # Grace time is consumed once per excursion, not reset at every leg
        # boundary, so it's always computed against the cumulative outside
        # time. The per-leg maximum penalty (below) is a separate, genuinely
        # per-leg concept: it caps how much a single leg may newly contribute,
        # not how much grace that leg gets.
        total_outside_time = self.excursion_total_outside_seconds + outside_time_this_segment

        penalty_time = np.round(max(0.0, total_outside_time - self.corridor_grace_time))
        total_penalty = self.scorecard.corridor_outside_penalty * penalty_time
        incremental_penalty = max(0, total_penalty - self.excursion_accumulated_score)

        is_capped = False
        if self.corridor_maximum_penalty_is_per_leg and self.scorecard.corridor_maximum_penalty > 0:
            if incremental_penalty > self.scorecard.corridor_maximum_penalty:
                incremental_penalty = self.scorecard.corridor_maximum_penalty
                is_capped = True

        return incremental_penalty, outside_time_this_segment, is_capped

    def check_and_apply_outside_penalty(
        self, position: ContestantReceivedPosition, gate: Gate, current_time: Optional[datetime.datetime] = None
    ):
        event_time = current_time or position.time
        if self.crossed_outside_time is None:
            return
        leg_incremental, leg_seconds, is_capped = self._calculate_current_leg_penalty(event_time)
        self.excursion_accumulated_score += leg_incremental
        self.excursion_total_outside_seconds += leg_seconds
        if is_capped:
            self.excursion_any_leg_capped = True
        if self.corridor_maximum_penalty_is_per_leg and self.crossed_outside_gate is not None:
            display_name = self.crossed_outside_gate.name if getattr(self.crossed_outside_gate, "is_visible", True) else "Secret"
            capped_this_leg = is_capped or (
                self.scorecard.corridor_maximum_penalty > 0 and leg_incremental >= self.scorecard.corridor_maximum_penalty
            )
            cap_str = " (capped)" if capped_this_leg else ""
            self.excursion_leg_details.append(f"{display_name}: {float(leg_incremental):.1f}{cap_str}")
        total_penalty = self.excursion_accumulated_score
        if current_time is not None and position.time != event_time:
            start_time_ref = self.current_leg_outside_start_time or self.crossed_outside_time
            display_leg_seconds = max(0.0, (position.time - start_time_ref).total_seconds()) if start_time_ref else leg_seconds
            total_seconds = (self.excursion_total_outside_seconds - leg_seconds) + display_leg_seconds
        else:
            total_seconds = self.excursion_total_outside_seconds
        cap_str = " (capped)" if self.excursion_any_leg_capped else ""
        details_str = ", ".join(self.excursion_leg_details)
        if details_str:
            details_str = f". Leg scores: [{details_str}]"
        if total_penalty > 0 or total_seconds > self.corridor_grace_time:
            self.update_score(
                UpdateScoreMessage(
                    event_time,
                    gate,
                    total_penalty,
                    f"outside corridor ({int(np.round(total_seconds))} s){details_str}. Total: {total_penalty}{cap_str}",
                    position.latitude,
                    position.longitude,
                    ANOMALY,
                    self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                )
            )
        self.last_outside_penalty = total_penalty
        self.last_finalized_time = event_time
        self.crossed_outside_time = None
        self.current_leg_outside_start_time = None
        self.excursion_accumulated_score = 0.0
        self.excursion_total_outside_seconds = 0.0
        self.excursion_any_leg_capped = False
        self.excursion_leg_details = []
        self.leg_penalties.clear()
        self.leg_seconds.clear()
        self.accumulated_score = 0

    def check_outside_corridor(self, track: List[ContestantReceivedPosition], gate: Gate):
        if len(track) == 0:
            return
        if self._check_inside_polygon(track[-1]):
            if self.corridor_state == self.OUTSIDE_CORRIDOR:
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
                penalty_position = self.crossed_outside_position or track[-1]
                self.check_and_apply_outside_penalty(penalty_position, gate)
            else:
                self.previous_corridor_state = self.INSIDE_CORRIDOR
                self.corridor_state = self.INSIDE_CORRIDOR
        else:
            if self.corridor_state == self.INSIDE_CORRIDOR:
                self.previous_corridor_state = self.INSIDE_CORRIDOR
                self.corridor_state = self.OUTSIDE_CORRIDOR
                self.crossed_outside_time = track[-1].time
                self.current_leg_outside_start_time = track[-1].time
                self.crossed_outside_gate = gate
                self.crossed_outside_position = track[-1]
                self.accumulated_score = 0
                self.update_score(
                    UpdateScoreMessage(
                        track[-1].time,
                        gate,
                        0,
                        "exiting corridor",
                        track[-1].latitude,
                        track[-1].longitude,
                        INFORMATION,
                        self.OUTSIDE_CORRIDOR_PENALTY_TYPE,
                    )
                )
            else:
                self.previous_corridor_state = self.OUTSIDE_CORRIDOR
                self.corridor_state = self.OUTSIDE_CORRIDOR
                self.crossed_outside_position = track[-1]
                leg_incremental, _, _ = self._calculate_current_leg_penalty(track[-1].time)
                self.accumulated_score = leg_incremental

    def on_adaptive_start(self, event: AdaptiveStartEvent):
        pass

    def finalise(self, track: List[ContestantReceivedPosition]):
        if self.corridor_state == self.OUTSIDE_CORRIDOR and track:
            # Fall back to the route's first waypoint (matching the pattern
            # already used for the auxiliary route-compliance checks above)
            # when no gate has been captured for this excursion at all -
            # e.g. the track started outside the corridor before any gate
            # context existed.
            fallback_gate = self.crossed_outside_gate
            if fallback_gate is None and self.route.waypoints:
                fallback_gate = self.route.waypoints[0]
            self.check_and_apply_outside_penalty(track[-1], fallback_gate)
