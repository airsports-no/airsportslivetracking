import datetime
import logging
from datetime import timedelta
from multiprocessing import Queue
from typing import List, Optional

from display.calculators.calculator import Calculator, GatekeeperState, GatekeeperEvent
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
    ):
        super().__init__(contestant, scorecard, gates, route, score_processing_queue)
        self.inside_zones = {}
        self.zones_scored = set()
        self.gates = gates
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None
        waypoint = self.contestant.navigation_task.route.waypoints[0]
        self.zone_helpers = [] # List of (zone_pk, helper, polygon)
        self.running_penalty = {}
        self.zone_map = {}
        self.prohibited_zone_grace_time = timedelta(seconds=self.scorecard.prohibited_zone_grace_time)
        zones = route.prohibited_set.filter(type="prohibited")
        logger.info(f"{self.contestant}: Found {len(zones)} prohibited zones for route {route.pk}")
        for zone in zones:
            self.zone_map[zone.pk] = zone
            # Create a helper centered on this zone's first point for better UTM precision
            helper = PolygonHelper(zone.path[0][0], zone.path[0][1])
            poly = helper.build_polygon(zone.path)
            self.zone_helpers.append((zone.pk, helper, poly))
            logger.info(f"{self.contestant}: Loaded prohibited zone {zone.name} (pk={zone.pk}) with {len(zone.path)} points")
        # logger.debug("Prohibited zones loaded: %s", str(i.name for i in self.zone_map.values()))
        # logger.debug("Prohibited zone polygons: %s", self.zone_polygons)

    def passed_finishpoint(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
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
        shortest_time = LOOKAHEAD_SECONDS
        
        for zone_pk, helper, poly in self.zone_helpers:
            time = get_shortest_intersection_time(
                track, helper, [(zone_pk, poly)], LOOKAHEAD_SECONDS
            )
            if time < shortest_time:
                shortest_time = time
                
        return 99 * (LOOKAHEAD_SECONDS - shortest_time) / LOOKAHEAD_SECONDS

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
        inside_this_time = set()
        
        for zone_pk, helper, poly in self.zone_helpers:
            is_inside = helper.check_inside_polygons([(zone_pk, poly)], position.latitude, position.longitude)
            if is_inside:
                inside_this_time.add(zone_pk)
                # logger.info(f"{self.contestant}: Inside zone {zone_pk} at {position.time}")
                
                if zone_pk not in self.inside_zones:
                    self.inside_zones[zone_pk] = position.time
                if (
                    zone_pk not in self.zones_scored
                    and position.time > self.inside_zones[zone_pk] + self.prohibited_zone_grace_time
                ):
                    self.zones_scored.add(zone_pk)
                    penalty = self.scorecard.prohibited_zone_penalty
                    self.running_penalty[zone_pk] = penalty
                    zone_name = self.zone_map[zone_pk].name
                    self.update_score(
                        UpdateScoreMessage(
                            position.time,
                            last_gate or self.gates[0],
                            penalty,
                            "entered prohibited zone {}".format(zone_name),
                            position.latitude,
                            position.longitude,
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
                try:
                    self.zones_scored.remove(zone)
                except KeyError:
                    pass
