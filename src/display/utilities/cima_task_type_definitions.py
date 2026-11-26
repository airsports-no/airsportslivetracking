import logging
from dataclasses import dataclass
from typing import Optional

from display.utilities.navigation_task_type_definitions import (  # noqa: F401  (re-exported)
    AIRSPORT_CHALLENGE,
    AIRSPORTS,
    ANR_CORRIDOR,
    LANDING,
    NAVIGATION_TASK_TYPES,
    POKER,
    PRECISION,
)
from display.utilities.task_types import (  # noqa: F401  (re-exported, the names are imported from here elsewhere)
    ANR_CATALOGUE,
    CIMA_ANR_SCORECARD,
    CIMA_PRECISION_SCORECARD,
    CIRCLE,
    CONTRACT_NAVIGATION_TIME_CONTROLS,
    CURVE_NAVIGATION_TIME_ESTIMATION,
    DURATION,
    KNOWN_CIRCUIT,
    LEGACY_AIRSPORT_CHALLENGE,
    LEGACY_AIRSPORTS,
    LEGACY_ANR_CORRIDOR,
    LEGACY_LANDING,
    LEGACY_POKER,
    LEGACY_PRECISION,
    LIMITED_FUEL_TURNPOINT_HUNT,
    PRECISION_NAVIGATION,
    TASK_TYPE_REGISTRY,
    TURNPOINT_HUNT,
    UNKNOWN_LEGS,
    TaskTypeDefinition,
    task_types_in_family,
)

logger = logging.getLogger(__name__)

# The tables below are views derived from display.utilities.task_types.TASK_TYPE_REGISTRY, the single source of truth.

# Task subtypes with no authored route backbone: the route consists entirely of free-map markers, so no Route.waypoints
# can be derived from the editable route's track. These get an empty placeholder Route.
NO_BACKBONE_TASK_SUBTYPES = tuple(key for key, item in TASK_TYPE_REGISTRY.items() if not item.has_backbone)

# Task subtype -> the declaration_payload key holding predicted gate times as absolute timestamps.
# See TaskTypeDefinition.absolute_time_declaration_key.
ABSOLUTE_TIME_DECLARATION_SUBTYPES = {
    key: item.absolute_time_declaration_key
    for key, item in TASK_TYPE_REGISTRY.items()
    if item.absolute_time_declaration_key is not None
}

# Task subtypes where the contestant must declare before flying.
DECLARATION_REQUIRED_SUBTYPES = frozenset(key for key, item in TASK_TYPE_REGISTRY.items() if item.declaration_required)


@dataclass(frozen=True)
class TaskSubtypeDefinition:
    key: str
    display_name: str
    coarse_family: str
    requires_contestant_configuration: bool = False
    required_primitives: tuple[str, ...] = ()
    # Primitives that, if present on the route, make it incompatible with this
    # subtype (for example a corridor task type cannot accept dummy/unknown-leg
    # waypoints). See route_compatibility.get_blocking_reasons.
    forbidden_primitives: tuple[str, ...] = ()
    declaration_schema_key: str | None = None
    scoring_modules: tuple[str, ...] = ()
    # The shortcut_name of the original scorecard the task is created from. None offers the scorecards of the
    # coarse family that no subtype claims (the legacy ones).
    scorecard_shortcut_name: str | None = None

    @classmethod
    def from_task_type(cls, item: TaskTypeDefinition) -> "TaskSubtypeDefinition":
        return cls(
            key=item.key,
            display_name=item.display_name,
            coarse_family=item.coarse_family,
            requires_contestant_configuration=item.requires_contestant_configuration,
            required_primitives=item.required_primitives,
            forbidden_primitives=item.forbidden_primitives,
            declaration_schema_key=item.declaration_schema_key,
            scoring_modules=item.scoring_modules,
            scorecard_shortcut_name=item.scorecard_shortcut_name,
        )


TASK_SUBTYPE_DEFINITIONS: dict[str, TaskSubtypeDefinition] = {
    key: TaskSubtypeDefinition.from_task_type(item) for key, item in TASK_TYPE_REGISTRY.items()
}

LEGACY_DEFAULT_SUBTYPE_BY_FAMILY: dict[str, str] = {
    item.coarse_family: item.key for item in TASK_TYPE_REGISTRY.values() if item.default_for_family
}


_TASK_TYPE_LABELS = dict(NAVIGATION_TASK_TYPES)


def get_task_subtype_definition(key: str) -> TaskSubtypeDefinition:
    try:
        return TASK_SUBTYPE_DEFINITIONS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown task subtype '{key}'") from exc


def describe_task_subtype(navigation_task) -> Optional[dict]:
    """
    The task's coarse family (e.g. "precision"/"Precision") and its specific subtype (e.g. "2.A1 Curve navigation with
    time estimation") for display, e.g. on TaskCard.tsx and in the apps' Register today list. None when the task has no
    subtype, or one that is not (or no longer) defined, so that one odd task cannot break a whole list.
    """
    try:
        definition = navigation_task.subtype_definition
    except ValueError:
        logger.warning(
            "Navigation task %s has an unknown task subtype %r", navigation_task.pk, navigation_task.task_subtype
        )
        return None
    if definition is None:
        return None
    return {
        "key": definition.key,
        "display_name": definition.display_name,
        "coarse_family": definition.coarse_family,
        "coarse_family_label": _TASK_TYPE_LABELS.get(definition.coarse_family, definition.coarse_family),
        "requires_contestant_configuration": definition.requires_contestant_configuration,
    }


def is_valid_task_subtype(key: str | None) -> bool:
    if key in (None, ""):
        return True
    return key in TASK_SUBTYPE_DEFINITIONS


def get_task_subtypes_for_family(coarse_family: str) -> list[TaskSubtypeDefinition]:
    return [TASK_SUBTYPE_DEFINITIONS[item.key] for item in task_types_in_family(coarse_family)]


def validate_subtype_family_compatibility(subtype: str | None, coarse_family: str) -> None:
    if subtype in (None, ""):
        return
    definition = get_task_subtype_definition(subtype)
    if definition.coarse_family != coarse_family:
        raise ValueError(f"Task subtype '{subtype}' is not compatible with coarse family '{coarse_family}'")


def get_default_task_subtype_for_family(coarse_family: str) -> str | None:
    return LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(coarse_family)


SUBTYPE_SCORECARD_SHORTCUT_NAMES = frozenset(
    definition.scorecard_shortcut_name
    for definition in TASK_SUBTYPE_DEFINITIONS.values()
    if definition.scorecard_shortcut_name is not None
)


def scorecard_suits_task_subtype(shortcut_name: str, subtype: str | None) -> bool:
    """
    Whether a task of [subtype] may be created from the original scorecard [shortcut_name]: a subtype with its own
    scorecard only from that one, any other task (legacy, or a subtype without one) only from a scorecard no subtype
    claims. The coarse family is checked separately (Scorecard.task_type).
    """
    definition = TASK_SUBTYPE_DEFINITIONS.get(subtype) if subtype else None
    if definition is not None and definition.scorecard_shortcut_name is not None:
        return shortcut_name == definition.scorecard_shortcut_name
    return shortcut_name not in SUBTYPE_SCORECARD_SHORTCUT_NAMES


# (score_sorting_direction, initial_score) of the task scorecard copy, for the subtypes whose catalogue maximum is a
# fixed constant and whose calculators emit properly signed penalty magnitudes. See
# TaskTypeDefinition.scoring_baseline and fixed_scale_factor.
CIMA_SCORING_BASELINE: dict[str, tuple[str, float]] = {
    key: item.scoring_baseline for key, item in TASK_TYPE_REGISTRY.items() if item.scoring_baseline is not None
}

# Uniform per-message scale factor for subtypes whose catalogue Qmax is a fixed constant rather than route-dependent.
# 2.A8 starts at 2000 points and P = 1000 * Q / 2000: the scorecard starts at 1000 and every score message is halved,
# so 1000 - sum(halved penalties) == (2000 - sum(penalties)) / 2.
CIMA_FIXED_SCALE_FACTORS: dict[str, float] = {
    key: item.fixed_scale_factor for key, item in TASK_TYPE_REGISTRY.items() if item.fixed_scale_factor is not None
}


def get_cima_fixed_scale_factor(subtype: str | None) -> float | None:
    """
    A constant multiplier to apply to every score message for this subtype (see
    CIMA_FIXED_SCALE_FACTORS), or None if this subtype doesn't use one.
    """
    if subtype in (None, ""):
        return None
    return CIMA_FIXED_SCALE_FACTORS.get(subtype)


def get_cima_scoring_baseline(subtype: str | None) -> tuple[str, float] | None:
    """
    (score_sorting_direction, initial_score) to apply to a freshly-copied task scorecard for the
    given CIMA task subtype, or None if this subtype has no known fixed-maximum default (legacy
    tasks, an unrecognised/blank subtype, and the subtypes documented above as deliberately
    excluded all return None here - callers should leave the copied scorecard untouched).
    """
    if subtype in (None, ""):
        return None
    return CIMA_SCORING_BASELINE.get(subtype)
