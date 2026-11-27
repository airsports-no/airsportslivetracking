from queue import Queue
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from display.utilities.coordinate_utilities import Projector

from display.calculators.orchestrator import Orchestrator
from display.models import Contestant
from display.utilities.task_types import get_calculators_for_task


def calculator_factory(
    contestant: "Contestant",
    score_processing_queue: Queue,
    live_processing: bool = True,
    projector: Optional["Projector"] = None,
) -> "Orchestrator":
    return Orchestrator(
        contestant,
        score_processing_queue,
        get_calculators_for_task(contestant.navigation_task),
        live_processing=live_processing,
        projector=projector,
    )
