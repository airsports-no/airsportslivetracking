from django.contrib.auth.management import create_permissions
from django.db import migrations

# Matches what the production "ContestCreator" group actually has (attached by hand there,
# confirmed against the live group): full CRUD on both Contest and EditableRoute, not just
# add_contest (migration 0178). A fresh/dev database only had add_contest attached, so any other
# ContestCreator action - editing/deleting a contest, or anything in the route editor at all -
# hit a blanket 403 the moment a self-service "Become an Organizer" user tried it.
CONTEST_CREATOR_PERMISSIONS = (
    "add_contest",
    "change_contest",
    "view_contest",
    "delete_contest",
    "add_editableroute",
    "change_editableroute",
    "view_editableroute",
    "delete_editableroute",
)


def grant_full_contest_creator_permissions(apps, schema_editor):
    """
    Same class of bug as migration 0178 (which attached display.add_contest to the
    "ContestCreator" group): EditableRoutePermission.has_permission (display/permissions.py)
    unconditionally requires display.add_editableroute for every request to
    EditableRouteViewSet - GET list, the global-map-sources/task_compatibility actions, and
    POST create alike - regardless of HTTP method. Without this permission attached anywhere,
    a user who "Became an Organizer" (and so only had add_contest, from 0178) got a blanket 403
    the moment they opened the route editor, even before touching any specific route.

    Rather than add just add_editableroute, this brings a fresh/dev database's group in line with
    what production's ContestCreator group actually has attached by hand: full add/change/view/
    delete on both Contest and EditableRoute.

    Permission rows are normally created by Django's post_migrate signal, which only fires once,
    after the *entire* migrate run finishes - so on an incrementally-migrated database (every real
    deployment so far) these permissions have existed for years and a plain
    Permission.objects.filter(...) here is fine. But on a from-scratch database build (a fresh
    devcontainer, CI, or a new install), this migration runs before that signal has ever fired, so
    force permissions to exist for this app's current (migration-time) models first - see the
    matching comment in migration 0178 for the full explanation.

    Idempotent - safe to run even where some or all of these are already attached by hand
    (Group.permissions is a ManyToManyField; adding an already-present permission is a no-op).
    """
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    app_config = apps.get_app_config("display")
    app_config.models_module = True
    create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias)
    app_config.models_module = None

    group, _ = Group.objects.get_or_create(name="ContestCreator")
    permissions = Permission.objects.filter(content_type__app_label="display", codename__in=CONTEST_CREATOR_PERMISSIONS)
    group.permissions.add(*permissions)


def revert(apps, schema_editor):
    # Deliberately a no-op: removing these permissions from the group would silently revoke
    # contest-management and route-editor access from every user who has ever self-served through
    # "Become an Organizer" relying on it, which is not what reversing this migration should do.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0178_contestcreator_group_add_contest_permission"),
    ]

    operations = [
        migrations.RunPython(grant_full_contest_creator_permissions, revert),
    ]
