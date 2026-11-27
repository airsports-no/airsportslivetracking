import logging
import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, List, Optional

from display.calculators.calculator import Calculator, GatePassedEvent
from display.calculators.update_score_message import PENALTY, PERCENTAGE_PENALTY, UpdateScoreMessage
from display.flight_order_and_maps.effective_route_rendering import get_effective_route_waypoints
from display.models import ANOMALY, INFORMATION
from display.utilities.coordinate_utilities import bearing_difference, calculate_bearing, point_to_line_distance
from display.utilities.gate_definitions import CIRCLE_CENTER, CIRCLE_ENTRY, CIRCLE_EXIT, CIRCLE_START

logger = logging.getLogger(__name__)

# The catalogue's 2.A7 Pmax (documentation/cima/cima_task_catalog.md: "P = (Rmin/Rmax - 0,5) *
# 500 ... Pmax = 250"), and also this calculator's "lose the whole task" penalty for a
# disqualifying violation - both express the same maximum, so a single constant.
CIRCLE_MAXIMUM_SCORE = 250.0

# Unit of ContestantReceivedPosition.altitude: metres. Traccar reports metres, the live path stores them unchanged
# (position_processor_process -> Contestant.create_position_from_traccar), and the outward traffic feed
# (websocket_channels.transmit_airsports_position_data) and flight_analysis convert them to feet with this factor. The
# band of the rule and of the scorecard (circle_altitude_band_ft) is in feet, so the spread is converted explicitly.
FEET_PER_METRE = 3.28084

# 2.A7: the first 180 degrees after CM are for orientation only, the scoring starts at the entry line X reached after
# them. A crossing a few degrees short of 180 (the aircraft on the line at the half turn, GPS noise) still counts.
ORIENTATION_ARC_DEG = 180.0
FULL_CIRCLE_DEG = 360.0
ARC_TOLERANCE_DEG = 10.0
# The scored circle is 360 degrees; the second crossing of X is only accepted after most of them, so that the aircraft
# wobbling over the line at the start cannot end the arc. A flight that gets within ARC_TOLERANCE_DEG of the full 360
# and then turns off towards WP without crossing the line has flown the circle too.
SCORED_ARC_MINIMUM_DEG = 270.0
# The angle around CM is only followed from this distance on: right over CM it is undefined. The smaller of this and
# half the minimum radius of the scorecard is used, so a small configured minimum does not make the start noisy.
MINIMUM_TRACKING_RADIUS_M = 50.0
# Straight entry over SP and CM (the old limits of this calculator): within 20 degrees of the SP-CM bearing and passing
# within 75 m of CM.
ENTRY_BEARING_TOLERANCE_DEG = 20.0
ENTRY_CENTRE_DISTANCE_M = 75.0

# The aircraft is still on the straight run over CM while its angle around CM is within this of where it was when it
# passed CM.
STRAIGHT_RUN_MAXIMUM_PROGRESS_DEG = 45.0

NOT_STARTED, WAITING_FOR_FIRST_CROSSING, IN_SCORED_ARC, ARC_COMPLETED = range(4)


@dataclass
class _Anchor:
    """Where a score message is placed in the score log: the gate, the time and the position."""

    time: Any
    gate: Any
    latitude: float
    longitude: float


class CircleCalculator(Calculator):
    """
    2.A7 Circle. The aircraft overflies SP and CM in a straight line, banks left after CM and flies 540 degrees: the
    first 180 are not scored, the scored 360 start when the entry line X (the line through CM and the X marker) is
    crossed and end when it is crossed again in the same direction. Rmin and Rmax are taken over that arc only,
    P = (Rmin/Rmax - 0.5) x 500 with 250 as the maximum.

    The angle around CM is the signed progress since the aircraft passed CM (counter-clockwise positive), followed
    position by position; the direction of the circle, the half turn and the two crossings of X all follow from it. Per
    position the work is a few multiplications and comparisons and a handful of running minima and maxima, the track is
    never rescanned. The result is emitted when WP is passed, or by finalise if it never was.
    """

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
        # The straight entry judged at the crossing of the X gate, None while that has not happened.
        self.entry_line_valid: Optional[bool] = None
        self.disqualified = False
        self.result_emitted = False
        self._last_gate = None
        (
            self.center_lat,
            self.center_lon,
            self.start_lat,
            self.start_lon,
            self.entry_lat,
            self.entry_lon,
            self.start_names,
            self.entry_names,
            self.exit_names,
        ) = self._resolve_circle_geometry()
        self._prepare_frame()
        self._reset_progress()

    # ------------------------------------------------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------------------------------------------------

    def _prepare_frame(self) -> None:
        """The projected frame around CM: the unit vector of the approach (SP to CM) and of the entry line (CM to X)."""
        self._frame_ready = False
        if self.center_lat is None or self.start_lat is None:
            return
        center = self.projector.project_point(self.center_lat, self.center_lon)
        start = self.projector.project_point(self.start_lat, self.start_lon)
        self._cm = (center.projected_x, center.projected_y)
        approach = (self._cm[0] - start.projected_x, self._cm[1] - start.projected_y)
        length = math.hypot(*approach)
        if length < 1.0:
            return
        self._approach = (approach[0] / length, approach[1] / length)
        self._entry_line = self._approach
        if self.entry_lat is not None:
            entry = self.projector.project_point(self.entry_lat, self.entry_lon)
            direction = (entry.projected_x - self._cm[0], entry.projected_y - self._cm[1])
            length = math.hypot(*direction)
            if length >= 1.0:
                self._entry_line = (direction[0] / length, direction[1] / length)
        self._tracking_start_radius_m = min(MINIMUM_TRACKING_RADIUS_M, self.cima_config.circle_radius_min_m / 2.0)
        self._frame_ready = True

    def _reset_progress(self) -> None:
        self._last_position = None
        self.arc_state = NOT_STARTED
        self.tracking = False
        self.progress_deg = 0.0
        self._tracking_start_deg = 0.0
        self.maximum_progress_deg = 0.0
        self.clockwise = False
        self._previous = None  # (x, y, angle, side, altitude) relative to CM
        self.crossings = 0
        self.arc_direction = 0
        self.arc_start_progress_deg = 0.0
        self.arc_end_progress_deg = 0.0
        self.radius_min_m: Optional[float] = None
        self.radius_max_m: Optional[float] = None
        self.altitude_min_m: Optional[float] = None
        self.altitude_max_m: Optional[float] = None
        self.arc_samples = 0
        self.tracking_entry_valid: Optional[bool] = None
        self._snapshot = None

    # ------------------------------------------------------------------------------------------------------------
    # Calculator interface
    # ------------------------------------------------------------------------------------------------------------

    def finalise(self, track: List):
        """A flight that never reached the exit (or never completed the circle) still gets its result here."""
        if self.result_emitted:
            return
        if not (self.started or self.entered or track):
            return
        last = track[-1] if track else None
        gate = self._last_gate or SimpleNamespace(name=next(iter(self.exit_names), "CM"))
        if last is None:
            return
        self._evaluate(_Anchor(last.time, gate, last.latitude, last.longitude), via_exit=False)

    def calculate_enroute(self, track: List, state) -> List:
        if not track or not self.started or self.result_emitted:
            return []
        self._process_position(track[-1])
        return []

    def on_gate_passed(self, event: GatePassedEvent):
        if self.center_lat is None:
            return
        self._last_gate = event.gate
        start_names = self.start_names
        entry_names = self.entry_names
        exit_names = self.exit_names
        anchor = _Anchor(event.intersection_time, event.gate, event.position.latitude, event.position.longitude)

        if event.gate.name in start_names and not self.started:
            self.started = True
            self.start_position = event.position
            self.arc_state = WAITING_FOR_FIRST_CROSSING
            self._emit(anchor, 0, "circle start passed", INFORMATION, "circle_start")
            return

        if event.gate.name in entry_names and not self.started:
            self.entered = True
            self.entry_position = event.position
            self._disqualify(anchor, "circle entry before circle start", "circle_invalid_entry")
            self.result_emitted = True
            return

        if event.gate.name in entry_names and not self.entered:
            self.entered = True
            self.entry_position = event.position
            if self.tracking and abs(self.progress_deg - self._tracking_start_deg) > STRAIGHT_RUN_MAXIMUM_PROGRESS_DEG:
                # Crossed during the circle, not on the straight run: the entry is judged from the track.
                self._emit(anchor, 0, "circle entry passed", INFORMATION, "circle_entry")
                return
            self.entry_line_valid = self._is_valid_straight_entry()
            if not self.entry_line_valid:
                self._disqualify(anchor, "circle entry not flown over SP and CM", "circle_invalid_entry_line")
                return
            self._emit(anchor, 0, "circle entry passed", INFORMATION, "circle_entry")
            return

        if event.gate.name in exit_names and not self.entered and not self._arc_completed():
            self.exited = True
            self._disqualify(anchor, "circle exit before circle entry", "circle_invalid_exit")
            self.result_emitted = True
            return

        if event.gate.name in exit_names and not self.exited:
            self.exited = True
            if not self.result_emitted:
                # The position that crossed WP may be the one that closed the arc and has not reached
                # calculate_enroute yet.
                self._process_position(event.position)
                self._evaluate(anchor, via_exit=True)

    # ------------------------------------------------------------------------------------------------------------
    # Geometry
    # ------------------------------------------------------------------------------------------------------------

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
            entry = by_type[CIRCLE_ENTRY][0] if by_type.get(CIRCLE_ENTRY) else None
            return (
                center.latitude,
                center.longitude,
                start.latitude,
                start.longitude,
                entry.latitude if entry else None,
                entry.longitude if entry else None,
                {waypoint.name for waypoint in by_type.get(CIRCLE_START, [])},
                {waypoint.name for waypoint in by_type.get(CIRCLE_ENTRY, [])},
                {waypoint.name for waypoint in by_type.get(CIRCLE_EXIT, [])},
            )
        logger.info(f"{self.contestant}: No compiled circle geometry, falling back to live EditableRoute")
        return self._resolve_circle_geometry_from_editable_route()

    def _resolve_circle_geometry_from_editable_route(self):
        editable_route = self.contestant.navigation_task.editable_route
        if not editable_route:
            return None, None, None, None, None, None, set(), set(), set()
        center_markers = editable_route.get_circle_center_markers()
        start_markers = editable_route.get_circle_start_markers()
        entry_markers = editable_route.get_circle_entry_markers()
        exit_markers = editable_route.get_circle_exit_markers()
        center_lat = center_lon = start_lat = start_lon = entry_lat = entry_lon = None
        if center_markers:
            center_lon, center_lat = center_markers[0]["geometry"]["coordinates"]
        if start_markers:
            start_lon, start_lat = start_markers[0]["geometry"]["coordinates"]
        if entry_markers:
            entry_lon, entry_lat = entry_markers[0]["geometry"]["coordinates"]
        start_names = {item["properties"].get("name") for item in start_markers} - {None}
        entry_names = {item["properties"].get("name") for item in entry_markers} - {None}
        exit_names = {item["properties"].get("name") for item in exit_markers} - {None}
        return center_lat, center_lon, start_lat, start_lon, entry_lat, entry_lon, start_names, entry_names, exit_names

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

    # ------------------------------------------------------------------------------------------------------------
    # Following the flight
    # ------------------------------------------------------------------------------------------------------------

    def _relative_xy(self, position):
        x, y = position.projected_x, position.projected_y
        if x is None or y is None:
            projected = self.projector.project_point(position.latitude, position.longitude)
            x, y = projected.projected_x, projected.projected_y
        return x - self._cm[0], y - self._cm[1]

    def _angle_deg(self, x: float, y: float) -> float:
        """Angle around CM from the direction of the straight run, counter-clockwise positive."""
        along = x * self._approach[0] + y * self._approach[1]
        return math.degrees(math.atan2(self._approach[0] * y - self._approach[1] * x, along))

    def _side(self, x: float, y: float) -> float:
        """Signed distance of a point (relative to CM) from the entry line X: positive on its left."""
        return self._entry_line[0] * y - self._entry_line[1] * x

    def _process_position(self, position) -> None:
        """
        Constant work per position: the angle around CM and the side of the entry line X against the previous position,
        and, inside the scored arc, the running Rmin, Rmax and altitude extremes.
        """
        if not self._frame_ready or position is self._last_position or self.arc_state in (NOT_STARTED, ARC_COMPLETED):
            return
        self._last_position = position
        x, y = self._relative_xy(position)
        radius = math.hypot(x, y)
        altitude = float(getattr(position, "altitude", 0) or 0)  # metres, see FEET_PER_METRE

        if not self.tracking:
            along = x * self._approach[0] + y * self._approach[1]
            if along > 0 and radius >= self._tracking_start_radius_m:
                # Past CM: from here the angle around CM is unambiguous. Zero is the direction of the straight run.
                self.tracking = True
                self.progress_deg = self._tracking_start_deg = self._angle_deg(x, y)
                self._previous = (x, y, self.progress_deg, self._side(x, y), altitude)
                self.tracking_entry_valid = self._is_straight_entry_by_track(x, y)
            return

        previous_x, previous_y, previous_angle, previous_side, previous_altitude = self._previous
        if radius < 1.0:
            return
        angle = self._angle_deg(x, y)
        step = (angle - previous_angle + 180.0) % 360.0 - 180.0
        side = self._side(x, y)
        progress_before = self.progress_deg
        self.progress_deg += step
        self.maximum_progress_deg = max(self.maximum_progress_deg, self.progress_deg)
        if self.progress_deg <= -(ORIENTATION_ARC_DEG - ARC_TOLERANCE_DEG):
            self.clockwise = True
        self._previous = (x, y, angle, side, altitude)

        if previous_side * side < 0:
            fraction = previous_side / (previous_side - side)
            crossing_radius = math.hypot(
                previous_x + fraction * (x - previous_x), previous_y + fraction * (y - previous_y)
            )
            crossing_altitude = previous_altitude + fraction * (altitude - previous_altitude)
            crossing_progress = progress_before + fraction * step
            direction = 1 if side > previous_side else -1
            if self.arc_state == WAITING_FOR_FIRST_CROSSING:
                if crossing_progress >= ORIENTATION_ARC_DEG - ARC_TOLERANCE_DEG:
                    self.arc_state = IN_SCORED_ARC
                    self.crossings = 1
                    self.arc_direction = direction
                    self.arc_start_progress_deg = crossing_progress
                    self._add_sample(crossing_radius, crossing_altitude)
            elif (
                self.arc_state == IN_SCORED_ARC
                and direction == self.arc_direction
                and crossing_progress - self.arc_start_progress_deg >= SCORED_ARC_MINIMUM_DEG
            ):
                self.crossings = 2
                self.arc_end_progress_deg = crossing_progress
                self._add_sample(crossing_radius, crossing_altitude)
                self.arc_state = ARC_COMPLETED
                return
        if self.arc_state == IN_SCORED_ARC:
            self._add_sample(radius, altitude)
            if self._snapshot is None and self.progress_deg - self.arc_start_progress_deg >= (
                FULL_CIRCLE_DEG - ARC_TOLERANCE_DEG
            ):
                # The measurements of the scored arc, see _arc_measurements.
                self._snapshot = (
                    self.radius_min_m,
                    self.radius_max_m,
                    self.altitude_min_m,
                    self.altitude_max_m,
                    self.progress_deg,
                )

    def _add_sample(self, radius: float, altitude: float) -> None:
        self.arc_samples += 1
        self.radius_min_m = radius if self.radius_min_m is None else min(self.radius_min_m, radius)
        self.radius_max_m = radius if self.radius_max_m is None else max(self.radius_max_m, radius)
        self.altitude_min_m = altitude if self.altitude_min_m is None else min(self.altitude_min_m, altitude)
        self.altitude_max_m = altitude if self.altitude_max_m is None else max(self.altitude_max_m, altitude)

    def _is_straight_entry_by_track(self, x: float, y: float) -> bool:
        """
        The straight entry judged from the track once the aircraft has passed CM, for a flight that never crossed the X
        gate: the line from the SP crossing to here must run along SP-CM and pass CM.
        """
        if self.start_position is None:
            return False
        start_x, start_y = self._relative_xy(self.start_position)
        dx, dy = x - start_x, y - start_y
        length = math.hypot(dx, dy)
        if length < 1.0:
            return False
        cosine = (dx * self._approach[0] + dy * self._approach[1]) / length
        if math.degrees(math.acos(max(-1.0, min(1.0, cosine)))) > ENTRY_BEARING_TOLERANCE_DEG:
            return False
        return abs(start_x * dy - start_y * dx) / length <= ENTRY_CENTRE_DISTANCE_M

    # ------------------------------------------------------------------------------------------------------------
    # The result
    # ------------------------------------------------------------------------------------------------------------

    def _evaluate(self, anchor: _Anchor, via_exit: bool) -> None:
        """Turns what was measured into the score log: a disqualification, or the circle score and the altitude rule."""
        if self.result_emitted:
            return
        self.result_emitted = True
        if self.disqualified:
            return
        config = self.cima_config
        reason = self._disqualifying_reason(config)
        if reason is not None:
            self._disqualify(anchor, *reason)
            return
        rmin, rmax, altitude_min, altitude_max, arc_end = self._arc_measurements()
        ratio = rmin / rmax
        score = min(CIRCLE_MAXIMUM_SCORE, (ratio - 0.5) * 500.0)
        lost = CIRCLE_MAXIMUM_SCORE - score
        self._emit(
            anchor,
            lost,
            f"circle lost {lost:.1f} of {CIRCLE_MAXIMUM_SCORE:.0f} points: Rmin {rmin:.0f} m, Rmax {rmax:.0f} m, "
            f"Rmin/Rmax {ratio:.3f} gives {score:.1f} points over the scored "
            f"{arc_end - self.arc_start_progress_deg:.0f} degrees",
            INFORMATION,
            "circle_score",
        )
        spread_ft = (altitude_max - altitude_min) * FEET_PER_METRE
        if spread_ft > config.circle_altitude_band_ft and config.circle_altitude_penalty_percent > 0:
            self._emit(
                anchor,
                config.circle_altitude_penalty_percent,
                f"circle altitude spread {spread_ft:.0f} ft is more than the "
                f"{config.circle_altitude_band_ft:g} ft band",
                ANOMALY,
                "circle_altitude_penalty",
                kind=PERCENTAGE_PENALTY,
            )
        if via_exit:
            self._emit(anchor, 0, "circle exit passed", INFORMATION, "circle_exit")

    def _arc_completed(self) -> bool:
        return self.arc_state == ARC_COMPLETED or (self.arc_state == IN_SCORED_ARC and self._snapshot is not None)

    def _arc_measurements(self) -> tuple:
        """
        (Rmin, Rmax, lowest and highest altitude in metres, progress at the end) of the scored arc. The measurements
        stop within ARC_TOLERANCE_DEG of the full 360 degrees: the aircraft turns off towards WP at the entry line, and
        the positions between the last one on the circle and the one across the line lie on the chord of that turn.
        """
        if self._snapshot is not None:
            return self._snapshot
        return (
            self.radius_min_m,
            self.radius_max_m,
            self.altitude_min_m,
            self.altitude_max_m,
            self.arc_end_progress_deg,
        )

    def _disqualifying_reason(self, config) -> Optional[tuple]:
        """(message, score type) of the first rule that costs the whole task, None for a valid circle."""
        if not self.started:
            return "circle not flown: the circle start (SP) was not passed", "circle_incomplete_scored_arc"
        entry_valid = self.entry_line_valid if self.entry_line_valid is not None else self.tracking_entry_valid
        if entry_valid is False:
            return "circle entry not flown over SP and CM", "circle_invalid_entry_line"
        if self.clockwise:
            return (
                f"circle flown clockwise (progress around CM {self.progress_deg:.0f} degrees)",
                "circle_invalid_direction",
            )
        if not self._arc_completed():
            if self.arc_state == IN_SCORED_ARC:
                done = self.progress_deg - self.arc_start_progress_deg
                detail = f"the entry line X was crossed once and not again, {done:.0f} of 360 degrees were flown"
            elif self.tracking:
                detail = (
                    "the entry line X was not crossed after the first 180 degrees, CM was circled "
                    f"{self.maximum_progress_deg:.0f} degrees"
                )
            else:
                detail = "the aircraft did not circle CM, the entry line X was never crossed"
            return f"circle scored arc not completed: {detail}", "circle_incomplete_scored_arc"
        rmin, rmax = self._arc_measurements()[:2]
        minimum, maximum = config.circle_radius_min_m, config.circle_radius_max_m
        if rmin < minimum or rmax > maximum:
            return (
                f"circle radius left the allowed {minimum:g}-{maximum:g} m: Rmin {rmin:.0f} m, Rmax {rmax:.0f} m",
                "circle_invalid_radius",
            )
        if rmin / rmax <= 0.5:
            return (
                f"circle Rmin/Rmax is {rmin / rmax:.3f}, 0.5 or lower (Rmin {rmin:.0f} m, Rmax {rmax:.0f} m)",
                "circle_invalid_score_ratio",
            )
        return None

    def _disqualify(self, anchor: _Anchor, message: str, score_type: str) -> None:
        self.disqualified = True
        self._emit(anchor, CIRCLE_MAXIMUM_SCORE, message, ANOMALY, score_type)

    def _emit(
        self, anchor: _Anchor, score: float, message: str, annotation_type: str, score_type: str, kind: str = PENALTY
    ):
        self.update_score(
            UpdateScoreMessage(
                anchor.time,
                anchor.gate,
                score,
                message,
                anchor.latitude,
                anchor.longitude,
                annotation_type,
                score_type,
                kind=kind,
            )
        )
