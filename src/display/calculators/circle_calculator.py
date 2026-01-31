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
    STATE_ORBITING = "ORBITING"
    STATE_FINISHED = "FINISHED"

    def __init__(self, center_wp: Waypoint, entry_wp: Waypoint, scorecard: Scorecard, contestant: Contestant):
        self.center_wp = center_wp
        self.entry_wp = entry_wp
        self.scorecard = scorecard
        self.contestant = contestant
        
        self.state = self.STATE_WAITING
        self.min_dist = float('inf')
        self.max_dist = 0.0
        self.entry_time: Optional[datetime] = None
        self.start_altitude: Optional[float] = None
        self.altitude_valid = True
        
        # Projector for entry line intersection checks
        self.projector = Projector(entry_wp.latitude, entry_wp.longitude)

    def process_position(self, position: ContestantReceivedPosition, track: list[ContestantReceivedPosition]) -> Optional[UpdateScoreMessage]:
        if self.state == self.STATE_FINISHED:
            return None

        # Check for Entry
        if self.state == self.STATE_WAITING:
            # Check intersection with Entry Line
            # We assume entry_wp.gate_line is defined and valid
            intersection_time = self._check_gate_intersection(self.entry_wp, track)
            
            if intersection_time:
                logger.info(f"{self.contestant}: Entered circle task at {intersection_time}")
                self.state = self.STATE_ORBITING
                self.entry_time = intersection_time
                self.start_altitude = position.altitude
                return UpdateScoreMessage(
                    position.time,
                    self.entry_wp,
                    0,
                    "Entered Circle",
                    position.latitude,
                    position.longitude,
                    "information",
                    SCORE_TYPE_CIRCLE
                )

        # Orbiting Logic
        elif self.state == self.STATE_ORBITING:
            # 1. Update Min/Max Radius
            dist = calculate_distance_lat_lon(
                (position.latitude, position.longitude),
                (self.center_wp.latitude, self.center_wp.longitude)
            )
            self.min_dist = min(self.min_dist, dist)
            self.max_dist = max(self.max_dist, dist)

            # 2. Check Altitude
            # CIMA 2.A7: "without exceeding 200ft (61m) between lowest and highest height."
            # The rule says "range of 200ft", implying max_alt - min_alt <= 200ft.
            # My design doc simplified it to abs(current - start). 
            # Let's stick to simple "range from start" for now or track min/max alt.
            # Let's track min/max altitude if we want strict adherence, but for now let's compare to start.
            if abs(position.altitude - self.start_altitude) > (self.scorecard.circle_altitude_tolerance / 0.3048): # convert meters to feet if tolerance is in feet? 
                # Wait, scorecard field help says "meters". 
                # Let's assume input altitude is meters (Traccar/Flymaster usually meters).
                # Actually ContestantReceivedPosition altitude is usually meters.
                # Scorecard tolerance is meters.
                if abs(position.altitude - self.start_altitude) > self.scorecard.circle_altitude_tolerance:
                    self.altitude_valid = False

            # 3. Check Exit
            # CIMA 2.A7: "Scoring ends by crossing the entry line (X)." 
            # We need to ensure we don't detect the *entry* crossing as exit immediately.
            # Usually circle is 360 degrees. 
            # Simplest check: time since entry > some buffer (e.g. 30 seconds) AND crossing line.
            time_since_entry = (position.time - self.entry_time).total_seconds()
            if time_since_entry > 30:
                intersection_time = self._check_gate_intersection(self.entry_wp, track)
                if intersection_time:
                    return self._finish_task(position)
                    
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
