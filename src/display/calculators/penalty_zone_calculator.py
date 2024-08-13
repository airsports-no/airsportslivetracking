import logging
from multiprocessing import Queue
from typing import List, Optional

from display.calculators.calculator import Calculator
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
        gates: List["Gate"],
        route: "Route",
        score_processing_queue: Queue,
    ):
        super().__init__(contestant, scorecard, gates, route, score_processing_queue)
        self.inside_zones = set()
        self.running_penalty = {}
        self.gates = gates
        self.crossed_outside_time = None
        self.last_outside_penalty = None
        self.crossed_outside_position = None
        waypoint = self.contestant.route.waypoints[0]
        self.polygon_helper = PolygonHelper(waypoint.latitude, waypoint.longitude)
        self.zone_polygons = []
        self.zone_map = {}
        self.entered_polygon_times = {}
        zones = route.prohibited_set.filter(type="penalty")
        for zone in zones:
            self.zone_map[zone.pk] = zone
            self.zone_polygons.append((zone.pk, self.polygon_helper.build_polygon(zone.path)))

    def passed_finishpoint(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        pass

    def calculate_outside_route(self, track: List[ContestantReceivedPosition], last_gate: "Gate"):
        self.check_inside_prohibited_zone(track, last_gate)

    def _calculate_danger_level(self, track: List[ContestantReceivedPosition]) -> float:
        """
        Danger level ranges from 0 to 100 where 100 is inside a penalty zone
        """
        LOOKAHEAD_SECONDS = 40
        shortest_time = get_shortest_intersection_time(
            track, self.polygon_helper, self.zone_polygons, LOOKAHEAD_SECONDS
        )
        return 99 * (LOOKAHEAD_SECONDS - shortest_time) / LOOKAHEAD_SECONDS

    def get_danger_level_and_accumulated_score(self, track: List[ContestantReceivedPosition]):
        # return 0, 0
        if len(self.entered_polygon_times) > 0:
            return 100, sum([0] + list(self.running_penalty.values()))
        else:
            return self._calculate_danger_level(track), sum([0] + list(self.running_penalty.values()))

    def calculate_enroute(
        self,
        track: List[ContestantReceivedPosition],
        last_gate: "Gate",
        in_range_of_gate: "Gate",
        next_gate: Optional["Gate"],
    ):
        self.check_inside_prohibited_zone(track, last_gate)

    def check_inside_prohibited_zone(self, track: List[ContestantReceivedPosition], last_gate: Optional["Gate"]):
        position = track[-1]
        zone_pks_the_position_was_already_inside = list(self.entered_polygon_times.keys())
        zone_pks_the_position_is_currently_inside = self.polygon_helper.check_inside_polygons(
            self.zone_polygons, position.latitude, position.longitude
        )
        for zone_pk in zone_pks_the_position_is_currently_inside:
            if zone_pk not in self.entered_polygon_times:
                self.entered_polygon_times[zone_pk] = position.time

        for zone_pk, start_time in dict(self.entered_polygon_times).items():
            self.running_penalty[zone_pk] = self.scorecard.calculate_penalty_zone_score(start_time, position.time)
            if zone_pk not in zone_pks_the_position_is_currently_inside:
                # Exiting the penalty zone, update the entry score
                self.update_score(
                    UpdateScoreMessage(
                        position.time,
                        self.get_last_non_secret_gate(last_gate or self.gates[0]),
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
                del self.running_penalty[zone_pk]
            elif zone_pk not in zone_pks_the_position_was_already_inside:
                # Entering the penalty zone
                self.update_score(
                    UpdateScoreMessage(
                        position.time,
                        self.get_last_non_secret_gate(last_gate or self.gates[0]),
                        0,
                        "entering penalty zone {}".format(self.zone_map[zone_pk].name),
                        position.latitude,
                        position.longitude,
                        INFORMATION,
                        self.INSIDE_PENALTY_ZONE_PENALTY_TYPE,
                    )
                )
