import logging
from typing import List, Optional

from display.models import Contestant
from display.models.scorecard_and_gate_score import Scorecard
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.waypoint import Waypoint
from display.calculators.update_score_message import UpdateScoreMessage
from display.utilities.coordinate_utilities import calculate_distance_lat_lon

logger = logging.getLogger(__name__)

SCORE_TYPE_FREE_POINT = "free_point_score"

class FreeNavigationCalculator:
    """
    Calculator for Free Waypoint tasks (e.g., Turnpoint Hunt 2.A6).
    Tracks visits to a set of unordered waypoints.
    """

    def __init__(self, free_waypoints: List[Waypoint], scorecard: Scorecard, contestant: Contestant):
        self.waypoints = free_waypoints
        self.scorecard = scorecard
        self.contestant = contestant
        self.visited_names = set()
        self.expected_order = self.contestant.declared_configuration.get("waypoint_order", [])
        self.next_expected_index = 0
        
        # CIMA 2.A3: Identify Middle Point for timing constraint
        self.mp_waypoint = next((wp for wp in self.contestant.navigation_task.route.waypoints if wp.type == 'mp'), None)
        self.mp_index_in_order = -1
        if self.mp_waypoint and self.expected_order:
            try:
                self.mp_index_in_order = self.expected_order.index(self.mp_waypoint.name)
            except ValueError:
                self.mp_index_in_order = -1

    def process_position(self, position: ContestantReceivedPosition, track: list[ContestantReceivedPosition]) -> Optional[UpdateScoreMessage]:
        
        for wp in self.waypoints:
            if wp.name in self.visited_names:
                continue
            
            # Check if inside range
            acceptance_radius = getattr(wp, 'radius', 0)
            if acceptance_radius == 0:
                acceptance_radius = 500 # Default 500m
                if wp.width > 0:
                    acceptance_radius = (wp.width * 1852) / 2
            
            distance = calculate_distance_lat_lon(
                (position.latitude, position.longitude),
                (wp.latitude, wp.longitude)
            )
            
            if distance <= acceptance_radius:
                
                # Check ordering if defined
                if self.expected_order:
                    if self.next_expected_index < len(self.expected_order):
                        expected_name = self.expected_order[self.next_expected_index]
                        
                        if wp.name == expected_name:
                            # CIMA 2.A3 Constraint: Waypoints after MP cannot be crossed before MP time
                            if self.mp_index_in_order != -1 and self.next_expected_index > self.mp_index_in_order:
                                actual_mp = self.contestant.actualgatetime_set.filter(gate=self.mp_waypoint.name).first()
                                if not actual_mp:
                                    logger.info(f"{self.contestant}: Ignoring {wp.name} as MP has not been passed yet.")
                                    return None

                            self.visited_names.add(wp.name)
                            self.next_expected_index += 1
                            logger.info(f"{self.contestant}: Visited ordered waypoint {wp.name}")
                            
                            return UpdateScoreMessage(
                                position.time,
                                wp,
                                round(self.scorecard.free_waypoint_score),
                                f"Visited {wp.name}",
                                position.latitude,
                                position.longitude,
                                "score",
                                SCORE_TYPE_FREE_POINT,
                                actual=position.time
                            )
                else:
                    self.visited_names.add(wp.name)
                    logger.info(f"{self.contestant}: Visited free waypoint {wp.name}")
                    
                    return UpdateScoreMessage(
                        position.time,
                        wp,
                        round(self.scorecard.free_waypoint_score),
                        f"Visited {wp.name}",
                        position.latitude,
                        position.longitude,
                        "score",
                        SCORE_TYPE_FREE_POINT,
                        actual=position.time
                    )
        
        return None
