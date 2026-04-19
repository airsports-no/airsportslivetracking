import datetime
import logging
from multiprocessing import Queue
from typing import List, Optional

from display.calculators.calculator import (
    Calculator,
    OrchestratorState,
    OrchestratorEvent,
    GateMissedEvent,
    FinishLinePassedEvent,
)
from display.calculators.calculator_utilities import PolygonHelper, get_shortest_intersection_time
from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route, INFORMATION, ANOMALY
from display.models.contestant_utility_models import ContestantReceivedPosition

logger = logging.getLogger(__name__)


class PenaltyZoneCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    INSIDE_PENALTY_ZONE_PENALTY_TYPE = "inside_penalty_zone"

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
        self.entered_polygon_times = {}
        self.entered_polygon_positions = {}
        self.polygon_helper = PolygonHelper(projector=self.projector)
        self.polygons = []  # List of (zone_pk, polygon)
        self.running_penalty = {}
        self.zone_map = {}
        zones = route.prohibited_set.filter(type="penalty")
        logger.info(f"{self.contestant}: Found {len(zones)} penalty zones for route {route.pk}")
        for zone in zones:
            self.zone_map[zone.pk] = zone
            poly = self.polygon_helper.build_polygon(zone.path)
            self.polygons.append((zone.pk, poly))
            logger.info(
                f"{self.contestant}: Loaded penalty zone {zone.name} (pk={zone.pk}) with {len(zone.path)} points"
            )

    def on_gate_missed(self, event: GateMissedEvent):
        pass

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        pass

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        self.check_inside_prohibited_zone(track, state.last_visible_gate)
        return []

    def _calculate_danger_level(self, track: List[ContestantReceivedPosition]) -> float:
        """
        Danger level ranges from 0 to 100 where 100 is inside a penalty zone
        """
        LOOKAHEAD_SECONDS = 40
        time = get_shortest_intersection_time(track, self.polygon_helper, self.polygons, LOOKAHEAD_SECONDS)
        return 99 * (LOOKAHEAD_SECONDS - time) / LOOKAHEAD_SECONDS

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]):
        # return 0, 0
        if len(self.entered_polygon_times) > 0:
            return 100, sum([0] + list(self.running_penalty.values()))
        else:
            return self._calculate_danger_level(track), sum([0] + list(self.running_penalty.values()))

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: OrchestratorState,
    ) -> List[OrchestratorEvent]:
        self.check_inside_prohibited_zone(track, state.last_visible_gate)
        return []

    def check_inside_prohibited_zone(self, track: List[ContestantReceivedPosition], last_visible_gate: Optional["Gate"]):
        position = track[-1]
        zone_pks_the_position_was_already_inside = list(self.entered_polygon_times.keys())

        p_x = getattr(position, "projected_x", None)
        p_y = getattr(position, "projected_y", None)

        zone_pks_the_position_is_currently_inside = self.polygon_helper.check_inside_polygons(self.polygons, p_x, p_y)

        for zone_pk in zone_pks_the_position_is_currently_inside:
            if zone_pk not in self.entered_polygon_times:
                self.entered_polygon_times[zone_pk] = position.time
                self.entered_polygon_positions[zone_pk] = (position.latitude, position.longitude)

        # Helper to get scoring gate context
        def get_scoring_gate(lv_gate):
            if lv_gate:
                # If it's a Gate object, use its is_visible property
                if hasattr(lv_gate, "is_visible"):
                    if lv_gate.is_visible:
                        return lv_gate
                # If it's a Waypoint object (fallback), check on_curved_segment
                elif not lv_gate.on_curved_segment:
                    return lv_gate

            # Fallback to first non-dummy waypoint
            waypoints = self.route.waypoints
            if waypoints:
                return next(
                    (w for w in waypoints if w.type != "dummy" and not w.on_curved_segment),
                    waypoints[0],
                )
            return None

        for zone_pk, start_time in dict(self.entered_polygon_times).items():
            self.running_penalty[zone_pk] = self.scorecard.calculate_penalty_zone_score(start_time, position.time)
            if zone_pk not in zone_pks_the_position_is_currently_inside:
                # Exiting the penalty zone, update the entry score
                self.update_score(
                    UpdateScoreMessage(
                        position.time,
                        get_scoring_gate(last_visible_gate),
                        self.running_penalty[zone_pk],
                        "inside penalty zone {} ({}s)".format(
                            self.zone_map[zone_pk].name, int((position.time - start_time).total_seconds())
                        ),
                        position.latitude,
                        position.longitude,
                        ANOMALY,
                        self.INSIDE_PENALTY_ZONE_PENALTY_TYPE,
                    )
                )
                # Clear information about being inside the zone
                del self.entered_polygon_times[zone_pk]
                del self.entered_polygon_positions[zone_pk]
                try:
                    del self.running_penalty[zone_pk]
                except KeyError:
                    pass
            elif zone_pk not in zone_pks_the_position_was_already_inside:
                # Entering the penalty zone
                entry_latitude, entry_longitude = self.entered_polygon_positions[zone_pk]
                self.update_score(
                    UpdateScoreMessage(
                        position.time,
                        get_scoring_gate(last_visible_gate),
                        0,
                        "entering penalty zone {}".format(self.zone_map[zone_pk].name),
                        entry_latitude,
                        entry_longitude,
                        INFORMATION,
                        self.INSIDE_PENALTY_ZONE_PENALTY_TYPE,
                    )
                )
    def finalise(self, track: List[ContestantReceivedPosition]):
        pass
