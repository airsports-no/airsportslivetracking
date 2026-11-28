from django.db import migrations


def clear_prefilled_intent(apps, schema_editor):
    """
    Routes saved before the intent was only what the author chose had it pre-filled with every compatible task type.
    An intent of several types that equals the stored compatible set is read as "not chosen" and cleared. Only the
    intent column is updated (no save(), so no signals and no recomputation).
    """
    EditableRoute = apps.get_model("display", "EditableRoute")
    for route in EditableRoute.objects.only("id", "intended_task_types", "compatible_task_types").iterator(
        chunk_size=500
    ):
        intended = route.intended_task_types or []
        if len(intended) > 1 and set(intended) == set(route.compatible_task_types or []):
            EditableRoute.objects.filter(pk=route.pk).update(intended_task_types=[])


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0219_contest_overall_result_method"),
    ]

    operations = [
        migrations.RunPython(clear_prefilled_intent, migrations.RunPython.noop),
    ]
