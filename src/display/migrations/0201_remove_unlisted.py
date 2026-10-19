from django.db import migrations, models


def unlisted_becomes_private(apps, schema_editor):
    """
    Unlisted (public, not featured) is gone: what was reachable by a link alone is private now. Afterwards is_featured
    simply mirrors is_public.
    """
    for model_name in ("Contest", "NavigationTask"):
        model = apps.get_model("display", model_name)
        model.objects.filter(is_public=True, is_featured=False).update(is_public=False)
        model.objects.filter(is_public=True).update(is_featured=True)
        model.objects.filter(is_public=False).update(is_featured=False)


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0200_contestant_mock_positions_at"),
    ]

    operations = [
        migrations.RunPython(unlisted_becomes_private, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contest",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="A public contest is visible to everybody, also people who are not logged in. A private contest is only visible to the people given access to it.",
            ),
        ),
        migrations.AlterField(
            model_name="contest",
            name="is_featured",
            field=models.BooleanField(
                default=False, help_text="Always equal to is_public (kept for the apps that still read it)."
            ),
        ),
        migrations.AlterField(
            model_name="navigationtask",
            name="is_public",
            field=models.BooleanField(
                default=False,
                help_text="A public navigation task is visible to everybody (if its contest is public too). A private one is only visible to the people given access to the contest.",
            ),
        ),
        migrations.AlterField(
            model_name="navigationtask",
            name="is_featured",
            field=models.BooleanField(
                default=False, help_text="Always equal to is_public (kept for the apps that still read it)."
            ),
        ),
    ]
