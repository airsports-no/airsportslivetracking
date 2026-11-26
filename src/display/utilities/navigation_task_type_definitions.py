from display.utilities.task_types import (
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    FAMILY_CHOICES,
    LANDING,
    POKER,
    PRECISION,
    default_task_type_for_family,
)

__all__ = [
    "AIRSPORT_CHALLENGE",
    "AIRSPORTS",
    "ANR_CORRIDOR",
    "DEFAULT_SCORECARD_SHORTCUT_NAMES",
    "LANDING",
    "NAVIGATION_TASK_TYPES",
    "POKER",
    "PRECISION",
]

NAVIGATION_TASK_TYPES = FAMILY_CHOICES

# The scorecard (by shortcut_name) a new task of a family is given unless the organiser picks another one: it is listed
# first in the scorecard picker, which preselects the first entry. A family without an entry lists the newest scorecard
# first (Scorecard.Meta.ordering).
DEFAULT_SCORECARD_SHORTCUT_NAMES = {
    family: shortcut_name
    for family, _label in FAMILY_CHOICES
    if (shortcut_name := default_task_type_for_family(family).family_default_scorecard_shortcut_name) is not None
}
