"""
Duplicate a navigation task (GitHub #23): a new task in the same or another contest with its own name, route and time
window, and everything else the organiser has set up copied from the original. That means the task type and its settings,
the scorecard with any changes made to it, and the flight order configuration. Contestants, the schedule and the
visibility are not copied: the copy starts private and empty, as a newly created task does.
"""

import datetime
from typing import Optional

from django.core.exceptions import ValidationError as CoreValidationError
from django.db import transaction
from guardian.shortcuts import assign_perm
from rest_framework.exceptions import PermissionDenied, ValidationError

from display.models import Contest, EditableRoute, MyUser, NavigationTask
from display.services.capacity_enforcement import assert_can_add_navigation_task
from display.services.route_compatibility import (
    assert_route_compatible_with_task_type,
    effective_subtype_key,
    extract_route_primitives,
    get_blocking_reasons,
)
from display.utilities.clone_object import simple_clone

# Set for the new task, not copied: what makes it a new occurrence, what belongs to the old one, and what is worked out
NOT_COPIED = {
    "id",
    "name",
    "contest",
    "route",
    "scorecard",
    "editable_route",
    "start_time",
    "finish_time",
    "schedule_start_time",
    "is_public",
    "is_featured",
    "_nominatim",
}


def copied_fields(source: NavigationTask) -> dict:
    """The settings of [source] that a duplicate gets, by field name."""
    return {
        field.attname if field.is_relation else field.name: getattr(source, field.attname)
        for field in NavigationTask._meta.concrete_fields
        if field.name not in NOT_COPIED
    }


def contests_to_duplicate_into(user: MyUser, source: NavigationTask):
    """
    The contests [user] may add the copy to: those they have been given to manage, and always the contest of [source]
    (a superuser manages every contest without a grant, and should not get all of them listed).
    """
    from guardian.shortcuts import get_objects_for_user

    managed = get_objects_for_user(
        user, "display.change_contest", klass=Contest, accept_global_perms=False, with_superuser=False
    )
    return (managed | Contest.objects.filter(pk=source.contest_id)).distinct().order_by("-start_time")


def route_choices(source: NavigationTask, user: MyUser) -> list[dict]:
    """The user's routes, each saying whether it fits the task type of [source] and, if not, why."""
    subtype_key = effective_subtype_key(source.original_scorecard.calculator, source.task_subtype)
    choices = []
    from guardian.shortcuts import get_objects_for_user

    # The routes the user has been given, not every route in the system as a superuser would get
    routes = get_objects_for_user(
        user, "display.change_editableroute", klass=EditableRoute, accept_global_perms=False, with_superuser=False
    )
    if source.editable_route_id:
        routes = routes | EditableRoute.objects.filter(pk=source.editable_route_id)
    for route in routes.distinct().order_by("-pk"):
        try:
            reasons = get_blocking_reasons(extract_route_primitives(route), subtype_key, route)
        except Exception:
            # A route that cannot even be read is not a choice, but must not break the list
            reasons = ["The route could not be read."]
        choices.append({"id": route.pk, "name": route.name, "compatible": not reasons, "reasons": reasons})
    return choices


def duplicate_navigation_task(
    source: NavigationTask,
    user: MyUser,
    *,
    contest: Contest,
    name: str,
    editable_route: EditableRoute,
    start_time: Optional[datetime.datetime] = None,
    finish_time: Optional[datetime.datetime] = None,
) -> NavigationTask:
    """A new task like [source] in [contest], flying [editable_route]. The time window defaults to that of [source]."""
    if not user.has_perm("display.change_contest", source.contest):
        raise PermissionDenied("Only somebody who manages the contest can duplicate its tasks.")
    if not user.has_perm("display.change_contest", contest):
        raise PermissionDenied("You can only put the copy in a contest you manage.")
    if not EditableRoute.get_for_user(user).filter(pk=editable_route.pk).exists():
        raise PermissionDenied("You can only use a route you can edit.")
    name = (name or "").strip()
    if not name:
        raise ValidationError({"name": "The new task needs a name."})
    # The task's results are kept under its name, so two tasks of a contest cannot share one
    if NavigationTask.objects.filter(contest=contest, name=name).exists():
        raise ValidationError({"name": f"The contest already has a task called {name}."})
    start_time = start_time or source.start_time
    finish_time = finish_time or source.finish_time
    if finish_time <= start_time:
        raise ValidationError({"finish_time": "The task must finish after it starts."})

    task_type = source.original_scorecard.calculator
    assert_can_add_navigation_task(contest, task_subtype=source.task_subtype, user=user)
    try:
        assert_route_compatible_with_task_type(editable_route, task_type, source.task_subtype)
    except CoreValidationError as e:
        raise ValidationError({"editable_route": e.messages})

    with transaction.atomic():
        try:
            route = editable_route.create_route(
                task_type,
                source.scorecard,
                source.route.rounded_corners,
                source.route.corridor_width,
                task_subtype=source.task_subtype,
            )
        except CoreValidationError as e:
            raise ValidationError({"editable_route": e.messages})
        for permission in ("view_route", "change_route", "delete_route"):
            assign_perm(f"display.{permission}", user, route)
        task = NavigationTask.create(
            **copied_fields(source),
            name=name,
            contest=contest,
            route=route,
            editable_route=editable_route,
            start_time=start_time,
            finish_time=finish_time,
            is_public=False,
        )
        _copy_scorecard(source, task)
        _copy_flight_order_configuration(source, task)
    task._creation_warnings = editable_route.get_validation_errors(corridor_width=source.route.corridor_width)
    return task


def _copy_scorecard(source: NavigationTask, task: NavigationTask) -> None:
    """The new task's scorecard becomes a copy of the source's own, changes included, keeping its own name and row."""
    own = task.scorecard
    simple_clone(
        source.scorecard,
        {"name": own.name, "shortcut_name": own.shortcut_name, "original": False},
        existing_clone=own,
    )
    task.refresh_from_db()
    if hasattr(task, "tasktest"):
        # The results service sorts the task as the scorecard does, which the copied scorecard may have changed
        direction = task.scorecard.score_sorting_direction
        task.tasktest.sorting = direction
        task.tasktest.save(update_fields=["sorting"])
        task.tasktest.task.summary_score_sorting_direction = direction
        task.tasktest.task.save(update_fields=["summary_score_sorting_direction"])


def _copy_flight_order_configuration(source: NavigationTask, task: NavigationTask) -> None:
    original = getattr(source, "flightorderconfiguration", None)
    own = getattr(task, "flightorderconfiguration", None)
    if original is None or own is None:
        return
    simple_clone(original, {"navigation_task": task}, existing_clone=own)
