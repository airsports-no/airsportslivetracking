"""
Task-template ("task_template") choice building for the task-type picker shared by every
navigation-task-creation entry point (the Django wizards in ``display.views_wizards`` and, going
forward, the REST endpoints backing the React SPA replacement).

A "task template" is either a coarse legacy family (``precision``, ``anr_corridor``, ...) or a
specific CIMA subtype key. ``normalize_task_template_selection`` turns whichever was picked into
the ``(task_type, task_subtype)`` pair the rest of the codebase expects.
"""

from django.core.exceptions import ValidationError

from display.services.route_compatibility import (
    extract_route_primitives,
    get_blocking_reasons,
    get_compatible_task_subtypes,
)
from display.services.task_type_visibility import can_user_see_task_subtype
from display.utilities.cima_task_type_definitions import LEGACY_DEFAULT_SUBTYPE_BY_FAMILY, TASK_SUBTYPE_DEFINITIONS
from display.utilities.navigation_task_type_definitions import NAVIGATION_TASK_TYPES


def task_template_choices(user=None, editable_route=None):
    """
    Build the grouped (Legacy/CIMA) task_template choices for the task-type picker.

    When `editable_route` is given, choices are additionally hard-filtered to task subtypes the
    route's authored content actually satisfies (display.services.route_compatibility) - this is
    the canonical, non-bypassable gate; user-permission filtering (CIMA visibility) is layered on
    top of it.
    """
    compatible = set(get_compatible_task_subtypes(editable_route)) if editable_route is not None else None
    grouped = {"Legacy": [], "CIMA": []}
    for key, label in NAVIGATION_TASK_TYPES:
        if compatible is not None and LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(key) not in compatible:
            continue
        grouped["Legacy"].append((key, label))
    for definition in TASK_SUBTYPE_DEFINITIONS.values():
        if definition.key.startswith("legacy_"):
            continue
        if not can_user_see_task_subtype(user, task_subtype=definition.key):
            continue
        if compatible is not None and definition.key not in compatible:
            continue
        grouped["CIMA"].append((definition.key, definition.display_name))
    return [(group, choices) for group, choices in grouped.items() if choices]


def no_compatible_task_types_message(user, editable_route) -> str | None:
    """
    When a route has zero task types compatible with it (given the caller's own visibility),
    explain why by naming the closest match - the visible subtype with the fewest missing route
    features - rather than leaving the task_template dropdown empty with no explanation.
    """
    primitives = extract_route_primitives(editable_route)
    candidates = []
    for key, label in NAVIGATION_TASK_TYPES:
        legacy_key = LEGACY_DEFAULT_SUBTYPE_BY_FAMILY.get(key)
        if legacy_key is None:
            continue
        candidates.append((label, get_blocking_reasons(primitives, legacy_key, editable_route)))
    for definition in TASK_SUBTYPE_DEFINITIONS.values():
        if definition.key.startswith("legacy_"):
            continue
        if not can_user_see_task_subtype(user, task_subtype=definition.key):
            continue
        candidates.append((definition.display_name, get_blocking_reasons(primitives, definition.key, editable_route)))
    if not candidates:
        return None
    label, reasons = min(candidates, key=lambda item: len(item[1]))
    if not reasons:
        # Choices weren't actually empty - nothing to explain.
        return None
    return f'This route is not compatible with any task type yet. The closest match, "{label}", still needs: {"; ".join(reasons)}.'


def normalize_task_template_selection(value):
    """Turn a picked task_template value (a coarse family key or a CIMA subtype key) into the
    (task_type, task_subtype) pair the rest of the codebase expects."""
    if not value:
        return None, None
    if value in dict(NAVIGATION_TASK_TYPES):
        return value, ""
    definition = TASK_SUBTYPE_DEFINITIONS.get(value)
    if definition is None:
        raise ValidationError("Select a valid task type.")
    return definition.coarse_family, definition.key
