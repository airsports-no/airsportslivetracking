from django.db import migrations


def grant_add_contest_permission(apps, schema_editor):
    """
    The self-service "Become an Organizer" flow (display.views.upgrade_to_organizer) adds the
    requesting user to a "ContestCreator" group, but nothing ever attached any permissions to that
    group - so clicking the button "succeeded" (redirected to the success page) without actually
    granting display.add_contest. Every test in this codebase instead grants add_contest directly
    to a user, which is how this went unnoticed: the group path was never exercised end-to-end.

    Idempotent - safe to run even where this has already been fixed by hand (Group.permissions is
    a ManyToManyField; adding an already-present permission is a no-op).
    """
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

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
