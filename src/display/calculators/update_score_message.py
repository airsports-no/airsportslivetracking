import datetime
from dataclasses import dataclass
from typing import Optional

from display.calculators.positions_and_gates import Gate


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
