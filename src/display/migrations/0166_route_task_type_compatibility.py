from django.db import migrations, models


def backfill_compatible_and_intended_task_types(apps, schema_editor):
    """
    Compute compatible_task_types for every existing route against the canonical ruleset, and
    seed intended_task_types with that same set so nothing that worked before this migration
    becomes newly unreachable through the wizards.

    Deliberately imports the real EditableRoute model (rather than using the apps.get_model
    historical model) because the compatibility computation relies on the route's business-logic
    accessor methods (get_track(), get_takeoff_gates(), ...), which historical models don't carry.
    This migration is written and run alongside the model/ruleset it depends on, so that coupling
    is acceptable here.
    """
    from display.models import EditableRoute
    from display.services.route_compatibility import (
        ROUTE_COMPATIBILITY_RULESET_VERSION,
        get_compatible_task_subtypes,
    )

    for route in EditableRoute.objects.all().iterator():
        compatible = get_compatible_task_subtypes(route)
        EditableRoute.objects.filter(pk=route.pk).update(
            compatible_task_types=compatible,
            compatibility_ruleset_version=ROUTE_COMPATIBILITY_RULESET_VERSION,
            intended_task_types=compatible,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0165_alter_flightorderconfiguration_map_source"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="editableroute",
            name="route_type",
        ),
        migrations.AddField(
            model_name="editableroute",
            name="intended_task_types",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Task subtype keys (legacy shims and/or CIMA subtypes) this route was "
                    "designed for. User-declared and purely advisory - it never restricts which "
                    "task types can actually be created from this route; see "
                    "compatible_task_types for that. An empty list means the route creator has "
                    "not declared an intent."
                ),
            ),
        ),
        migrations.AddField(
            model_name="editableroute",
            name="compatible_task_types",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Task subtype keys this route's authored content actually satisfies the "
                    "requirements of, computed by display.services.route_compatibility from the "
                    "route's features. Canonical: this is what gates task-type/route selection "
                    "in the task creation wizards. Recomputed on every save()."
                ),
            ),
        ),
        migrations.AddField(
            model_name="editableroute",
            name="compatibility_ruleset_version",
            field=models.IntegerField(
                default=0,
                help_text="ROUTE_COMPATIBILITY_RULESET_VERSION compatible_task_types was last computed against.",
            ),
        ),
        migrations.RunPython(backfill_compatible_and_intended_task_types, noop_reverse),
    ]
