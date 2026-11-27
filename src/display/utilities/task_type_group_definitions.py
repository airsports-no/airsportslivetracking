from display.utilities.task_types import TASK_TYPE_REGISTRY, find_task_type

LEGACY_TASK_TYPE_GROUP = "legacy"
CIMA_TASK_TYPE_GROUP = "cima"


def get_task_type_group(task_type: str | None = None, task_subtype: str | None = None) -> str:
    if task_subtype:
        definition = find_task_type(task_subtype)
        if definition is None:
            return CIMA_TASK_TYPE_GROUP
        if definition.is_legacy:
            return LEGACY_TASK_TYPE_GROUP
        return CIMA_TASK_TYPE_GROUP
    return LEGACY_TASK_TYPE_GROUP


def get_fine_task_type_group(task_type: str | None = None, task_subtype: str | None = None) -> str:
    """Like get_task_type_group, but namespaced per-subtype for non-legacy
    subtypes (e.g. "cima:circle" instead of just "cima"). Used only by the
    access-enforcement path, which needs to be able to grant access to one
    specific CIMA task type rather than always all-or-nothing. Existing
    AccessGrant/TokenType rows only ever store the coarse "cima" string and
    keep granting every CIMA subtype unchanged; new grants may optionally use
    the namespaced form to scope to a single subtype.
    """
    coarse_group = get_task_type_group(task_type=task_type, task_subtype=task_subtype)
    if coarse_group != CIMA_TASK_TYPE_GROUP or not task_subtype:
        return coarse_group
    return f"{CIMA_TASK_TYPE_GROUP}:{task_subtype}"


def get_all_fine_task_type_groups() -> list[str]:
    """Every group string get_fine_task_type_group() can return: the coarse
    "legacy" group, the coarse "cima" group, and one namespaced "cima:<subtype>"
    group per non-legacy subtype. Used for admin choices and for the "grant
    everything" superuser/visibility-gate-off cases.
    """
    groups = {LEGACY_TASK_TYPE_GROUP, CIMA_TASK_TYPE_GROUP}
    for definition in TASK_TYPE_REGISTRY.values():
        if not definition.is_legacy:
            groups.add(f"{CIMA_TASK_TYPE_GROUP}:{definition.key}")
    return sorted(groups)
