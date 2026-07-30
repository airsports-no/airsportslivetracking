from display.utilities.cima_task_type_definitions import TASK_SUBTYPE_DEFINITIONS

LEGACY_TASK_TYPE_GROUP = "legacy"
CIMA_TASK_TYPE_GROUP = "cima"


def get_task_type_group(task_type: str | None = None, task_subtype: str | None = None) -> str:
    if task_subtype:
        definition = TASK_SUBTYPE_DEFINITIONS.get(task_subtype)
        if definition is None:
            return CIMA_TASK_TYPE_GROUP
        if definition.key.startswith("legacy_"):
            return LEGACY_TASK_TYPE_GROUP
        return CIMA_TASK_TYPE_GROUP
    return LEGACY_TASK_TYPE_GROUP
