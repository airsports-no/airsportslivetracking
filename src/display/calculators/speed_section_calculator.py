import logging
from datetime import datetime
from typing import List, Optional, Dict

from display.models import Contestant
from display.models.scorecard_and_gate_score import Scorecard
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.waypoint import Waypoint
from display.calculators.update_score_message import UpdateScoreMessage
from display.utilities.coordinate_utilities import calculate_distance_lat_lon, Projector

logger = logging.getLogger(__name__)

SCORE_TYPE_SPEED_SECTION = "speed_section_score"

class SpeedSectionCalculator:
    """
    Calculator for CIMA Speed Sections (2.A8, 3.A5, 3.B5).
    Calculates ground speed between Start and End points.
    """

    def __init__(self, start_waypoints: List[Waypoint], end_waypoints: List[Waypoint], scorecard: Scorecard, contestant: Contestant):
        self.scorecard = scorecard
        self.contestant = contestant
        
        # Organize into pairs by group_id
        self.sections: Dict[str, Dict] = {}
        for start in start_waypoints:
            if start.group_id:
                self.sections[start.group_id] = {
                    'start_wp': start,
                    'end_wp': next((e for e in end_waypoints if e.group_id == start.group_id), None),
                    'start_time': None,
                    'end_time': None,
                    'finished': False,
                    'projector': Projector(start.latitude, start.longitude)
                }

    def process_position(self, position: ContestantReceivedPosition, track: list[ContestantReceivedPosition]) -> Optional[UpdateScoreMessage]:
        if len(track) < 2:
            return None

        for group_id, section in self.sections.items():
            if section['finished'] or not section['end_wp']:
                continue

            # 1. Detect Start Crossing
            if not section['start_time']:
                intersection_time = section['start_wp'].get_gate_intersection_time(section['projector'], track)
                if intersection_time:
                    section['start_time'] = intersection_time
                    logger.info(f"{self.contestant}: Started speed section {group_id} at {intersection_time}")
                    return UpdateScoreMessage(
                        position.time, section['start_wp'], 0,
                        f"Started Speed Section ({group_id})",
                        position.latitude, position.longitude,
                        "information", SCORE_TYPE_SPEED_SECTION
                    )

            # 2. Detect End Crossing
            else:
                intersection_time = section['end_wp'].get_gate_intersection_time(section['projector'], track)
                if intersection_time:
                    section['end_time'] = intersection_time
                    section['finished'] = True
                    return self._calculate_section_results(group_id, position)

        return None

    def _calculate_section_results(self, group_id: str, position: ContestantReceivedPosition) -> UpdateScoreMessage:
        section = self.sections[group_id]
        start_wp = section['start_wp']
        end_wp = section['end_wp']
        
        duration_seconds = (section['end_time'] - section['start_time']).total_seconds()
        
        # Calculate distance in NM
        distance_nm = calculate_distance_lat_lon(
            (start_wp.latitude, start_wp.longitude),
            (end_wp.latitude, end_wp.longitude)
        ) / 1852.0
        
        if duration_seconds > 0:
            speed_kts = (distance_nm / duration_seconds) * 3600
        else:
            speed_kts = 0

        logger.info(f"{self.contestant}: Finished speed section {group_id}. Speed: {speed_kts:.2f} kts")

        # Scoring logic would go here based on task rules. 
        # For now, we report the speed as an information/score message.
        return UpdateScoreMessage(
            position.time, end_wp, 0,
            f"Speed Section {group_id}: {speed_kts:.1f} kts",
            position.latitude, position.longitude,
            "information", SCORE_TYPE_SPEED_SECTION,
            actual=section['end_time']
        )
