import datetime
from dataclasses import dataclass
from typing import Optional

from display.calculators.positions_and_gates import Gate

# What a score message does to the contestant's score. `score` is always a non-negative magnitude, except that a
# percentage penalty carries the percentage itself (50 is 50%).
PENALTY = "penalty"  # reduces the score
ACHIEVEMENT = "achievement"  # adds to the score
PERCENTAGE_PENALTY = "percentage_penalty"  # a percentage of the final task score, deducted after scoring is complete
SCORE_KINDS = (PENALTY, ACHIEVEMENT, PERCENTAGE_PENALTY)


@dataclass
class UpdateScoreMessage:
    time: datetime.datetime
    gate: Gate
    score: float
    message: str
    latitude: float
    longitude: float
    annotation_type: str
    score_type: str
    maximum_score: Optional[float] = None
    planned: Optional[datetime.datetime] = None
    actual: Optional[datetime.datetime] = None
    kind: str = PENALTY

    def __post_init__(self):
        if self.kind not in SCORE_KINDS:
            raise ValueError(f"Unknown score message kind '{self.kind}'")
