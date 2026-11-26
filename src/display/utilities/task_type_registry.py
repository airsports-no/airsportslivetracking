"""
The calculator pipeline per coarse family (Scorecard.calculator) as calculator_factory.py consumes it. The pipelines
themselves are defined per task type in task_types.TASK_TYPE_REGISTRY; this module only picks the right one for a
contestant's task.
"""

from typing import TYPE_CHECKING, Callable

from display.utilities.navigation_task_type_definitions import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    NAVIGATION_TASK_TYPES,
    POKER,
    PRECISION,
)
from display.utilities.task_types import PIPELINE_DEFAULT, TASK_TYPE_REGISTRY, default_task_type_for_family

if TYPE_CHECKING:
    from display.calculators.calculator import Calculator
    from display.models import Contestant

CalculatorListBuilder = Callable[["Contestant"], list[type["Calculator"]]]

# NAVIGATION_TASK_TYPES stays the single hand-authored source for these labels (it also feeds
# Scorecard.calculator's Django choices) - this just avoids typing the strings a second time.
_DISPLAY_NAMES = dict(NAVIGATION_TASK_TYPES)


class TaskTypeSpec:
    def __init__(self, calculator: str, build_calculators: CalculatorListBuilder):
        self.calculator = calculator
        self.display_name = _DISPLAY_NAMES[calculator]
        self.build_calculators = build_calculators


def _build_family_calculators(family: str) -> CalculatorListBuilder:
    """
    The calculator list of the contestant's task type within [family]: the task's stored subtype when it belongs to the
    family, else the family's default task type. The pipelines themselves live in task_types.TASK_TYPE_REGISTRY.
    """

    def build(contestant: "Contestant") -> list:
        definition = TASK_TYPE_REGISTRY.get(contestant.navigation_task.task_subtype)
        if definition is None or definition.coarse_family != family:
            definition = default_task_type_for_family(family)
        return definition.get_calculators()

    return build


def _build_default_calculators(contestant: "Contestant") -> list:
    from django.utils.module_loading import import_string

    return [import_string(path) for path in PIPELINE_DEFAULT]


TASK_TYPES: dict[str, TaskTypeSpec] = {
    family: TaskTypeSpec(family, _build_family_calculators(family))
    for family in (PRECISION, ANR_CORRIDOR, AIRSPORTS, AIRSPORT_CHALLENGE, LANDING, POKER)
}

# calculator_factory.py's fallback for any scorecard.calculator value with no TASK_TYPES entry
# (e.g. a legacy/custom value) - preserved as-is, not folded into TASK_TYPES since it isn't
# keyed by a real task type.
DEFAULT_CALCULATOR_BUILDER: CalculatorListBuilder = _build_default_calculators
