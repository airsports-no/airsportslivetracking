import logging
import math
from datetime import datetime
from typing import Optional

from display.models import Contestant
from display.models.scorecard_and_gate_score import Scorecard
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.waypoint import Waypoint
from display.calculators.update_score_message import UpdateScoreMessage
from display.utilities.coordinate_utilities import calculate_distance_lat_lon, Projector, nv_intersect

logger = logging.getLogger(__name__)

SCORE_TYPE_CIRCLE = "circle_score"

class CircleCalculator:
    """
    Calculator for CIMA Circle Task (2.A7).
    """

    STATE_WAITING = "WAITING"
    STATE_ORIENTING = "ORIENTING" # First 180 deg
    STATE_SCORING = "SCORING" # The 360 deg orbit
    STATE_FINISHED = "FINISHED"

    def __init__(self, center_wp: Waypoint, entry_wp: Waypoint, scorecard: Scorecard, contestant: Contestant):
        self.center_wp = center_wp
        self.entry_wp = entry_wp
        self.scorecard = scorecard
        self.contestant = contestant
        
        self.state = self.STATE_WAITING
        self.min_dist = float('inf')
        self.max_dist = 0.0
        self.min_alt = float('inf')
        self.max_alt = float('-inf')
        self.last_crossing_time: Optional[datetime] = None
        self.entry_crossings = 0
        self.altitude_valid = True
        
        # Projector for entry line intersection checks
        self.projector = Projector(entry_wp.latitude, entry_wp.longitude)

    def process_position(self, position: ContestantReceivedPosition, track: list[ContestantReceivedPosition]) -> Optional[UpdateScoreMessage]:
        if self.state == self.STATE_FINISHED:
            return None

        # Check for Entry Line Crossings
        intersection_time = self._check_gate_intersection(self.entry_wp, track)
        
        # Debounce crossings (minimum 20s between detections)
        is_valid_crossing = False
        if intersection_time:
            if not self.last_crossing_time or (intersection_time - self.last_crossing_time).total_seconds() > 20:
                is_valid_crossing = True
                self.last_crossing_time = intersection_time
                self.entry_crossings += 1

        if is_valid_crossing:
            if self.entry_crossings == 1:
                self.state = self.STATE_ORIENTING
                logger.info(f"{self.contestant}: Circle Phase 1 (Orientation) started at {intersection_time}")
                return UpdateScoreMessage(
                    position.time, self.entry_wp, 0, "Circle: Orienting (180 deg)",
                    position.latitude, position.longitude, "information", SCORE_TYPE_CIRCLE
                )
            
            elif self.entry_crossings == 2:
                self.state = self.STATE_SCORING
                logger.info(f"{self.contestant}: Circle Phase 2 (Scoring) started at {intersection_time}")
                return UpdateScoreMessage(
                    position.time, self.entry_wp, 0, "Circle: Scoring Orbit started",
                    position.latitude, position.longitude, "information", SCORE_TYPE_CIRCLE
                )
            
            elif self.entry_crossings == 3:
                return self._finish_task(position)

        # Active Task Monitoring
        if self.state in (self.STATE_ORIENTING, self.STATE_SCORING):
            # 1. Update Altitude Range (range < 61m)
            self.min_alt = min(self.min_alt, position.altitude)
            self.max_alt = max(self.max_alt, position.altitude)
            if (self.max_alt - self.min_alt) > self.scorecard.circle_altitude_tolerance:
                self.altitude_valid = False

            # 2. Update Min/Max Radius (Only in scoring phase)
            if self.state == self.STATE_SCORING:
                dist = calculate_distance_lat_lon(
                    (position.latitude, position.longitude),
                    (self.center_wp.latitude, self.center_wp.longitude)
                )
                self.min_dist = min(self.min_dist, dist)
                self.max_dist = max(self.max_dist, dist)
                    
        return None

    def _finish_task(self, position: ContestantReceivedPosition) -> UpdateScoreMessage:
        self.state = self.STATE_FINISHED
        logger.info(f"{self.contestant}: Finished circle task. Rmin={self.min_dist}, Rmax={self.max_dist}")

        # Calculate Score
        # P = (Rmin/Rmax - 0.5) * 500
        if self.max_dist == 0:
            ratio = 0
        else:
            ratio = self.min_dist / self.max_dist
        
        points = 0
        if ratio > self.scorecard.circle_min_radius_ratio:
            points = (ratio - 0.5) * self.scorecard.circle_performance_factor
        
        # Apply Altitude Penalty
        if not self.altitude_valid:
            penalty = points * self.scorecard.circle_altitude_penalty
            points -= penalty
            logger.info(f"{self.contestant}: Circle altitude violation. Penalty: {penalty}")

        return UpdateScoreMessage(
            position.time,
            self.center_wp,
            round(points),
            f"Circle Score (Ratio: {ratio:.2f})",
            position.latitude,
            position.longitude,
            "score",
            SCORE_TYPE_CIRCLE,
            actual=position.time 
        )

    def _check_gate_intersection(self, gate: Waypoint, track: list[ContestantReceivedPosition]) -> Optional[datetime]:
        """
        Helper to check if the last segment of the track intersected the gate line.
        """
        if len(track) < 2:
            return None
        
        return gate.get_gate_intersection_time(self.projector, track)
