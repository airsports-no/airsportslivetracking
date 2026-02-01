import logging
from datetime import datetime
from typing import Optional

from display.models import Contestant
from display.models.scorecard_and_gate_score import Scorecard
from display.models.contestant_utility_models import ContestantReceivedPosition
from display.waypoint import Waypoint
from display.calculators.update_score_message import UpdateScoreMessage

logger = logging.getLogger(__name__)

SCORE_TYPE_DURATION = "duration_score"

class DurationCalculator:
    """
    Calculator for CIMA Duration Task (2.B3).
    Measures time from first takeoff gate to last landing gate.
    """

    def __init__(self, scorecard: Scorecard, contestant: Contestant):
        self.scorecard = scorecard
        self.contestant = contestant
        self.takeoff_time: Optional[datetime] = None
        self.landing_time: Optional[datetime] = None
        self.finished = False

    def process_position(self, position: ContestantReceivedPosition, track: list[ContestantReceivedPosition]) -> Optional[UpdateScoreMessage]:
        if self.finished:
            return None

        # We rely on the parent Gatekeeper having already detected TO/LDG times
        # and recorded them in ActualGateTime. But for real-time feedback,
        # we can monitor the contestant's known gate crossings.
        
        # Check if takeoff has been recorded
        if not self.takeoff_time:
            actual_to = self.contestant.actualgatetime_set.filter(gate__icontains='Takeoff').first()
            if actual_to:
                self.takeoff_time = actual_to.time
                logger.info(f"{self.contestant}: Duration start detected at {self.takeoff_time}")

        # Check if landing has been recorded
        if self.takeoff_time and not self.landing_time:
            actual_ldg = self.contestant.actualgatetime_set.filter(gate__icontains='Landing').first()
            if actual_ldg:
                self.landing_time = actual_ldg.time
                self.finished = True
                
                duration = self.landing_time - self.takeoff_time
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                
                logger.info(f"{self.contestant}: Duration finished. Total: {minutes}m {seconds}s")
                
                return UpdateScoreMessage(
                    position.time, None, 0,
                    f"Total Duration: {minutes}m {seconds}s",
                    position.latitude, position.longitude,
                    "score", SCORE_TYPE_DURATION,
                    actual=self.landing_time
                )

        return None
