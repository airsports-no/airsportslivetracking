import datetime
import logging
from datetime import timedelta
from multiprocessing import Queue
from typing import List, Optional

from display.calculators.calculator import (
    Calculator,
    GatekeeperState,
    GatekeeperEvent,
    GateMissedEvent,
    FinishLinePassedEvent,
)
from display.calculators.calculator_utilities import PolygonHelper, get_shortest_intersection_time
from display.calculators.positions_and_gates import Gate
from display.calculators.update_score_message import UpdateScoreMessage
from display.models import Contestant, Scorecard, Route
from display.models.contestant_utility_models import ContestantReceivedPosition

logger = logging.getLogger(__name__)


class ProhibitedZoneCalculator(Calculator):
    """
    Implements https://www.fai.org/sites/default/files/documents/gac_2020_precision_flying_rules_final.pdf
    """

    INSIDE_PROHIBITED_ZONE_PENALTY_TYPE = "inside_prohibited_zone"

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
        self.inside_zones = {}
        self.inside_positions = {}
        self.zones_scored = set()
        self.gates = gates
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None

        self.polygon_helper = PolygonHelper(projector=self.projector)
        self.polygons = []  # List of (zone_pk, polygon)
        self.running_penalty = {}
        self.zone_map = {}
        self.prohibited_zone_grace_time = timedelta(seconds=self.scorecard.prohibited_zone_grace_time)
        zones = route.prohibited_set.filter(type="prohibited")
        logger.info(f"{self.contestant}: Found {len(zones)} prohibited zones for route {route.pk}")
        for zone in zones:
            self.zone_map[zone.pk] = zone
            poly = self.polygon_helper.build_polygon(zone.path)
            self.polygons.append((zone.pk, poly))
            logger.info(
                f"{self.contestant}: Loaded prohibited zone {zone.name} (pk={zone.pk}) with {len(zone.path)} points"
            )

    def on_gate_missed(self, event: GateMissedEvent):
        pass

    def passed_finishpoint(self, event: FinishLinePassedEvent):
        pass

    def calculate_outside_route(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        self.check_inside_prohibited_zone(track, state.last_gate)
        return []

    def _calculate_danger_level(self, track: List[ContestantReceivedPosition]) -> float:
        """
        Danger level ranges from 0 to 100 where 100 is inside a prohibited zone
        """
        LOOKAHEAD_SECONDS = 40
        time = get_shortest_intersection_time(track, self.polygon_helper, self.polygons, LOOKAHEAD_SECONDS)
        return 99 * (LOOKAHEAD_SECONDS - time) / LOOKAHEAD_SECONDS

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]):
        # return 0, 0
        if len(self.inside_zones) > 0:
            return 100, sum([0] + list(self.running_penalty.values()))
        else:
            return self._calculate_danger_level(track), sum([0] + list(self.running_penalty.values()))

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        state: GatekeeperState,
    ) -> List[GatekeeperEvent]:
        self.check_inside_prohibited_zone(track, state.last_gate)
        return []

    def check_inside_prohibited_zone(self, track: List[ContestantReceivedPosition], last_gate: Optional["Gate"]):
        position = track[-1]
        p_x = getattr(position, "projected_x", None)
        p_y = getattr(position, "projected_y", None)

        incursions = self.polygon_helper.check_inside_polygons(self.polygons, p_x, p_y)
        inside_this_time = set(incursions)

        for zone_pk in incursions:
            # logger.info(f"{self.contestant}: Inside zone {zone_pk} at {position.time}")

            if zone_pk not in self.inside_zones:
                self.inside_zones[zone_pk] = position.time
                self.inside_positions[zone_pk] = (position.latitude, position.longitude)
            if (
                zone_pk not in self.zones_scored
                and position.time > self.inside_zones[zone_pk] + self.prohibited_zone_grace_time
            ):
                self.zones_scored.add(zone_pk)
                penalty = self.scorecard.prohibited_zone_penalty
                self.running_penalty[zone_pk] = penalty
                zone_name = self.zone_map[zone_pk].name
                entry_latitude, entry_longitude = self.inside_positions[zone_pk]
                self.update_score(
                    UpdateScoreMessage(
                        position.time,
                        last_gate or self.gates[0],
                        penalty,
                        "entered prohibited zone {}".format(zone_name),
                        entry_latitude,
                        entry_longitude,
                        "anomaly",
                        f"{self.INSIDE_PROHIBITED_ZONE_PENALTY_TYPE}_{zone_name}",
                        maximum_score=self.scorecard.prohibited_zone_maximum,
                    )
                )

        for zone in list(self.inside_zones.keys()):
            if zone not in inside_this_time:
                try:
                    del self.running_penalty[zone]
                except KeyError:
                    pass
                del self.inside_zones[zone]
                del self.inside_positions[zone]
                try:
                    self.zones_scored.remove(zone)
                except KeyError:
                    pass
