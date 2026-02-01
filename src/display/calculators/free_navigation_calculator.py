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
