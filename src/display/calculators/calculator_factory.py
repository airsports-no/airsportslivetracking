from queue import Queue
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from display.utilities.coordinate_utilities import Projector

from display.calculators.orchestrator import Orchestrator
from display.models import Contestant
from display.utilities.task_type_registry import DEFAULT_CALCULATOR_BUILDER, TASK_TYPES


def calculator_factory(
    contestant: "Contestant",
    score_processing_queue: Queue,
    live_processing: bool = True,
    projector: Optional["Projector"] = None,
) -> "Orchestrator":
    spec = TASK_TYPES.get(contestant.navigation_task.scorecard.calculator)
    build_calculators = spec.build_calculators if spec else DEFAULT_CALCULATOR_BUILDER
    return Orchestrator(
        contestant,
        score_processing_queue,
        build_calculators(contestant),
        live_processing=live_processing,
        projector=projector,
    )
