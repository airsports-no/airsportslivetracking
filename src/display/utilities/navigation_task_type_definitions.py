"""
The coarse family constants under their old import path. Migrations 0174 and 0175 import them from here and migrations
are not edited; everything else imports them from display.utilities.task_types.
"""

from display.utilities.task_types import AIRSPORT_CHALLENGE, AIRSPORTS, ANR_CORRIDOR

__all__ = ["AIRSPORTS", "AIRSPORT_CHALLENGE", "ANR_CORRIDOR"]
