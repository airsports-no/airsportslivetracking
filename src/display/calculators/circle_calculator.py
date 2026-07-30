import math
from typing import List

from display.calculators.calculator import Calculator, GatePassedEvent
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import ANOMALY, INFORMATION
from display.utilities.coordinate_utilities import bearing_difference, calculate_bearing, point_to_line_distance


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
        payload = self._get_circle_payload()
        if not payload:
            return
        start_names = {item["properties"].get("name") for item in (payload.get("circle_start_marker") or [])}
        entry_names = {item["properties"].get("name") for item in (payload.get("circle_entry_marker") or [])}
        exit_names = {item["properties"].get("name") for item in (payload.get("circle_exit_marker") or [])}

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
            if not self._is_valid_straight_entry(payload):
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

    def _get_circle_payload(self) -> dict:
        editable_route = self.contestant.navigation_task.editable_route
        if not editable_route:
            return {}
        return {
            "circle_center_marker": editable_route.get_circle_center_markers(),
            "circle_start_marker": editable_route.get_circle_start_markers(),
            "circle_entry_marker": editable_route.get_circle_entry_markers(),
            "circle_exit_marker": editable_route.get_circle_exit_markers(),
        }

    def _is_valid_straight_entry(self, payload: dict) -> bool:
        if self.start_position is None or self.entry_position is None:
            return False
        start_markers = payload.get("circle_start_marker") or []
        center_markers = payload.get("circle_center_marker") or []
        if not start_markers or not center_markers:
            return False
        sp_lon, sp_lat = start_markers[0]["geometry"]["coordinates"]
        cm_lon, cm_lat = center_markers[0]["geometry"]["coordinates"]
        entry_bearing = calculate_bearing(
            (self.start_position.latitude, self.start_position.longitude),
            (self.entry_position.latitude, self.entry_position.longitude),
        )
        sp_cm_bearing = calculate_bearing((sp_lat, sp_lon), (cm_lat, cm_lon))
        if abs(bearing_difference(sp_cm_bearing, entry_bearing)) > 20:
            return False
        distance_m = point_to_line_distance(
            self.start_position.latitude,
            self.start_position.longitude,
            self.entry_position.latitude,
            self.entry_position.longitude,
            cm_lat,
            cm_lon,
        )
        return distance_m <= 75

    def _is_clockwise_turn(self, current_position) -> bool:
        if self.start_position is None or self.entry_position is None or current_position is None:
            return False
        center_markers = self._get_circle_payload().get("circle_center_marker") or []
        if not center_markers:
            return False
        cm_lon, cm_lat = center_markers[0]["geometry"]["coordinates"]
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
        center_markers = self._get_circle_payload().get("circle_center_marker") or []
        if not center_markers:
            return None
        cm_lon, cm_lat = center_markers[0]["geometry"]["coordinates"]
        center_projected = self.projector.project_point(cm_lat, cm_lon)
        return math.hypot(
            current_position.projected_x - center_projected.projected_x,
            current_position.projected_y - center_projected.projected_y,
        )

    def _record_progress_sample(self, position) -> None:
        if position is None:
            return
        center_markers = self._get_circle_payload().get("circle_center_marker") or []
        if not center_markers:
            return
        cm_lon, cm_lat = center_markers[0]["geometry"]["coordinates"]
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
