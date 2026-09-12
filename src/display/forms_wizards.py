# These three are no longer used in this module (their only callers, TaskTypeForm and
# ContestSelectForm, were removed once NewNavigationTaskWizard/RouteToTaskWizard were replaced by
# the React nav-task-creation flow) - kept as re-exports because existing tests still import them
# from here (display.forms_wizards._task_template_choices etc.) rather than from
# display.services.task_templates directly.
from display.services.task_templates import (  # noqa: F401
    no_compatible_task_types_message as _no_compatible_task_types_message,
)
from display.services.task_templates import (  # noqa: F401
    normalize_task_template_selection as _normalize_task_template_selection,
)
from display.services.task_templates import (  # noqa: F401
    task_template_choices as _task_template_choices,
)
