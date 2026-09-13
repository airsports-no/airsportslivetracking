from django.contrib.auth.management import create_permissions
from django.db import migrations


def grant_add_contest_permission(apps, schema_editor):
    """
    The self-service "Become an Organizer" flow (display.views.upgrade_to_organizer) adds the
    requesting user to a "ContestCreator" group, but nothing ever attached any permissions to that
    group - so clicking the button "succeeded" (redirected to the success page) without actually
    granting display.add_contest. Every test in this codebase instead grants add_contest directly
    to a user, which is how this went unnoticed: the group path was never exercised end-to-end.

    Permission rows are normally created by Django's post_migrate signal, which only fires once,
    after the *entire* migrate run finishes - so on an incrementally-migrated database (every
    real deployment so far) display.add_contest has existed for years and a plain
    Permission.objects.get(...) here is fine. But on a from-scratch database build (a fresh
    devcontainer, CI, or a new install), this migration runs before that signal has ever fired,
    and the plain get() crashes the whole `migrate` command with Permission.DoesNotExist. Force
    permissions to exist for this app's current (migration-time) models first, using the pattern
    Django's own docs recommend for this exact situation ("assigning permissions in a migration").

    Idempotent - safe to run even where this has already been fixed by hand (Group.permissions is
    a ManyToManyField; adding an already-present permission is a no-op).
    """
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    app_config = apps.get_app_config("display")
    app_config.models_module = True
    create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias)
    app_config.models_module = None

    group, _ = Group.objects.get_or_create(name="ContestCreator")
    add_contest_permission = Permission.objects.get(
        content_type__app_label="display",
        codename="add_contest",
    )
    group.permissions.add(add_contest_permission)


def revert(apps, schema_editor):
    # Deliberately a no-op: removing this permission from the group would silently revoke
    # contest-creation rights from every user who has ever self-served through "Become an
    # Organizer" relying on it, which is not what reversing this migration should do.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0177_navigationtask_display_navi_is_publ_4d1ba7_idx_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(grant_add_contest_permission, revert),
    ]
