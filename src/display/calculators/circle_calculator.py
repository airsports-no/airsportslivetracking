import logging
import math
from typing import List

from display.calculators.calculator import Calculator, GatePassedEvent
from display.calculators.update_score_message import UpdateScoreMessage
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.models import ANOMALY, INFORMATION
from display.utilities.coordinate_utilities import bearing_difference, calculate_bearing, point_to_line_distance
from display.utilities.gate_definitions import CIRCLE_CENTER, CIRCLE_ENTRY, CIRCLE_EXIT, CIRCLE_START

logger = logging.getLogger(__name__)


class CircleCalculator(Calculator):
    def __init__(
        self,
        contestant,
        scorecard,
        route,
        score_processing_queue,
        live_processing=True,
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
        self.started = False
        self.entered = False
        self.exited = False
        self.start_position = None
        self.entry_position = None
        self.radius_samples_m = []
        self.altitude_samples_ft = []
        self.progress_radius_samples = []
        self.last_circle_angle_deg = None
        self.cumulative_progress_deg = 0.0
        self.final_score_ready = False
        (
            self.center_lat,
            self.center_lon,
            self.start_lat,
            self.start_lon,
            self.start_names,
            self.entry_names,
            self.exit_names,
        ) = self._resolve_circle_geometry()

    def finalise(self, track: List):
        pass

    def calculate_enroute(self, track: List, state) -> List:
        if not self.entered or self.exited:
            return []
        if not track:
            return []
        self._record_progress_sample(track[-1])
        self._capture_altitude(track[-1])
        return []

    def on_gate_passed(self, event: GatePassedEvent):
        if self.center_lat is None:
            return
        start_names = self.start_names
        entry_names = self.entry_names
        exit_names = self.exit_names

        if event.gate.name in start_names and not self.started:
            self.started = True
            self.start_position = event.position
            self._emit(event, 0, "circle start passed", INFORMATION, "circle_start")
            return

        if event.gate.name in entry_names and not self.started:
            self.entered = True
            self.entry_position = event.position
            self._emit(event, 250, "circle entry before circle start", ANOMALY, "circle_invalid_entry")
            return

        if event.gate.name in entry_names and not self.entered:
            self.entered = True
            self.entry_position = event.position
            self.radius_samples_m = []
            self.altitude_samples_ft = []
            self.progress_radius_samples = []
            self.last_circle_angle_deg = None
            self.cumulative_progress_deg = 0.0
            self.final_score_ready = False
            if not self._is_valid_straight_entry():
                self._emit(event, 250, "circle entry not flown over SP and CM", ANOMALY, "circle_invalid_entry_line")
                return
            self._emit(event, 0, "circle entry passed", INFORMATION, "circle_entry")
            return

        if event.gate.name in exit_names and not self.entered:
            self.exited = True
            self._emit(event, 250, "circle exit before circle entry", ANOMALY, "circle_invalid_exit")
            return

        if event.gate.name in exit_names and self.entered and not self.exited:
            self.exited = True
            self._record_progress_sample(event.position)
            radius_m = self._calculate_radius_m(event.position)
            if radius_m is not None:
                self.radius_samples_m.append(radius_m)
            self._capture_altitude(event.position)
            if self._is_clockwise_turn(event.position):
                self._emit(event, 250, "circle flown clockwise", ANOMALY, "circle_invalid_direction")
                return
            if self._is_radius_outside_limits(event.position):
                self._emit(event, 250, "circle radius outside allowed limits", ANOMALY, "circle_invalid_radius")
                return
            if self._has_invalid_score_ratio():
                self._emit(event, 250, "circle score ratio outside allowed limits", ANOMALY, "circle_invalid_score_ratio")
                return
            if self._is_center_outside_flown_circle():
                self._emit(event, 250, "circle center marker outside flown circle", ANOMALY, "circle_invalid_center")
                return
            if not self._has_completed_scored_arc():
                self._emit(event, 250, "circle scored arc not completed", ANOMALY, "circle_incomplete_scored_arc")
                return
            score = self._calculate_circle_score()
            self._emit(event, score, f"circle score {score:.1f} points", INFORMATION, "circle_score")
            altitude_penalty = self._calculate_altitude_penalty(score)
            if altitude_penalty > 0:
                self._emit(event, altitude_penalty, "circle altitude spread penalty", ANOMALY, "circle_altitude_penalty")
            self._emit(event, 0, "circle exit passed", INFORMATION, "circle_exit")

    def _resolve_circle_geometry(self):
        """Groups the compiled effective waypoints (see
        contestant_task_compiler.CircleStrategy) by role. Falls back to
        reading the live EditableRoute for contestants compiled before that
        strategy existed.
        """
        by_type = {}
        for waypoint in get_effective_route_waypoints(self.contestant.navigation_task, contestant=self.contestant):
            by_type.setdefault(waypoint.type, []).append(waypoint)
        if CIRCLE_CENTER in by_type and CIRCLE_START in by_type:
            center = by_type[CIRCLE_CENTER][0]
            start = by_type[CIRCLE_START][0]
            return (
                center.latitude,
                center.longitude,
                start.latitude,
                start.longitude,
                {waypoint.name for waypoint in by_type.get(CIRCLE_START, [])},
                {waypoint.name for waypoint in by_type.get(CIRCLE_ENTRY, [])},
                {waypoint.name for waypoint in by_type.get(CIRCLE_EXIT, [])},
            )
        logger.info(f"{self.contestant}: No compiled circle geometry, falling back to live EditableRoute")
        return self._resolve_circle_geometry_from_editable_route()

    def _resolve_circle_geometry_from_editable_route(self):
        editable_route = self.contestant.navigation_task.editable_route
        if not editable_route:
            return None, None, None, None, set(), set(), set()
        center_markers = editable_route.get_circle_center_markers()
        start_markers = editable_route.get_circle_start_markers()
        entry_markers = editable_route.get_circle_entry_markers()
        exit_markers = editable_route.get_circle_exit_markers()
        center_lat = center_lon = start_lat = start_lon = None
        if center_markers:
            center_lon, center_lat = center_markers[0]["geometry"]["coordinates"]
        if start_markers:
            start_lon, start_lat = start_markers[0]["geometry"]["coordinates"]
        start_names = {item["properties"].get("name") for item in start_markers} - {None}
        entry_names = {item["properties"].get("name") for item in entry_markers} - {None}
        exit_names = {item["properties"].get("name") for item in exit_markers} - {None}
        return center_lat, center_lon, start_lat, start_lon, start_names, entry_names, exit_names

    def _is_valid_straight_entry(self) -> bool:
        if self.start_position is None or self.entry_position is None:
            return False
        if self.start_lat is None or self.center_lat is None:
            return False
        entry_bearing = calculate_bearing(
            (self.start_position.latitude, self.start_position.longitude),
            (self.entry_position.latitude, self.entry_position.longitude),
        )
        sp_cm_bearing = calculate_bearing((self.start_lat, self.start_lon), (self.center_lat, self.center_lon))
        if abs(bearing_difference(sp_cm_bearing, entry_bearing)) > 20:
            return False
        distance_m = point_to_line_distance(
            self.start_position.latitude,
            self.start_position.longitude,
            self.entry_position.latitude,
            self.entry_position.longitude,
            self.center_lat,
            self.center_lon,
        )
        return distance_m <= 75

    def _is_clockwise_turn(self, current_position) -> bool:
        if self.start_position is None or self.entry_position is None or current_position is None:
            return False
        if self.center_lat is None:
            return False
        cm_lon, cm_lat = self.center_lon, self.center_lat
        entry_angle = math.atan2(self.entry_position.latitude - cm_lat, self.entry_position.longitude - cm_lon)
        current_angle = math.atan2(current_position.latitude - cm_lat, current_position.longitude - cm_lon)
        delta = current_angle - entry_angle
        while delta <= -math.pi:
            delta += 2 * math.pi
        while delta > math.pi:
            delta -= 2 * math.pi
        return delta < -1e-6

    def _is_radius_outside_limits(self, current_position) -> bool:
        radius_m = self._calculate_radius_m(current_position)
        if radius_m is None:
            return False
        min_radius = float(getattr(self.scorecard, "circle_radius_min_m", 200) or 200)
        max_radius = float(getattr(self.scorecard, "circle_radius_max_m", 750) or 750)
        return radius_m < min_radius or radius_m > max_radius

    def _calculate_radius_m(self, current_position):
        if current_position is None:
            return None
        if self.center_lat is None:
            return None
        center_projected = self.projector.project_point(self.center_lat, self.center_lon)
        return math.hypot(
            current_position.projected_x - center_projected.projected_x,
            current_position.projected_y - center_projected.projected_y,
        )

    def _record_progress_sample(self, position) -> None:
        if position is None:
            return
        if self.center_lat is None:
            return
        cm_lon, cm_lat = self.center_lon, self.center_lat
        angle_deg = math.degrees(math.atan2(position.latitude - cm_lat, position.longitude - cm_lon))
        if self.last_circle_angle_deg is None:
            self.last_circle_angle_deg = angle_deg
            return
        delta = angle_deg - self.last_circle_angle_deg
        while delta <= -180:
            delta += 360
        while delta > 180:
            delta -= 360
        self.cumulative_progress_deg += abs(delta)
        self.last_circle_angle_deg = angle_deg
        if self.cumulative_progress_deg >= 540:
            self.final_score_ready = True
        radius_m = self._calculate_radius_m(position)
        if radius_m is None:
            return
        if self.cumulative_progress_deg <= 180:
            return
        if self.cumulative_progress_deg > 540:
            return
        self.progress_radius_samples.append(radius_m)

    def _capture_altitude(self, position) -> None:
        altitude_ft = getattr(position, "altitude", 0) or 0
        self.altitude_samples_ft.append(float(altitude_ft))

    def _calculate_circle_score(self) -> float:
        samples = [sample for sample in self.progress_radius_samples if sample is not None and sample > 0]
        if not samples:
            samples = [sample for sample in self.radius_samples_m if sample is not None and sample > 0]
        if not samples:
            return 250.0
        rmin = min(samples)
        rmax = max(samples)
        if rmax <= 0:
            return 250.0
        ratio = rmin / rmax
        score = (ratio - 0.5) * 500
        return max(0.0, min(250.0, round(score, 1)))

    def _has_invalid_score_ratio(self) -> bool:
        samples = [sample for sample in self.progress_radius_samples if sample is not None and sample > 0]
        if not samples:
            samples = [sample for sample in self.radius_samples_m if sample is not None and sample > 0]
        if not samples:
            return False
        rmin = min(samples)
        rmax = max(samples)
        if rmax <= 0:
            return True
        return (rmin / rmax) <= 0.5

    def _is_center_outside_flown_circle(self) -> bool:
        samples = [sample for sample in self.progress_radius_samples if sample is not None and sample > 0]
        if not samples:
            samples = [sample for sample in self.radius_samples_m if sample is not None and sample > 0]
        if not samples:
            return False
        if self._has_invalid_score_ratio():
            return True
        return False

    def _has_completed_scored_arc(self) -> bool:
        return self.final_score_ready and len(self.progress_radius_samples) > 0

    def _calculate_altitude_penalty(self, score: float) -> float:
        if len(self.altitude_samples_ft) < 2:
            return 0.0
        spread = max(self.altitude_samples_ft) - min(self.altitude_samples_ft)
        if spread <= 200:
            return 0.0
        return round(score * 0.2, 1)

    def _emit(self, event: GatePassedEvent, score: float, message: str, annotation_type: str, score_type: str):
        self.update_score(
            UpdateScoreMessage(
                event.intersection_time,
                event.gate,
                score,
                message,
                event.position.latitude,
                event.position.longitude,
                annotation_type,
                score_type,
                planned=getattr(event.gate, "expected_time", None),
                actual=event.intersection_time,
            )
        )
