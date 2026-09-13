from django.db import migrations, models

# The old, corrupted TRACKING_PILOT_AND_COPILOT value (see
# display.utilities.tracking_definitions) - this migration only ever needs the literal string,
# not the (now-fixed) live constant, since it's rewriting rows that still hold this exact value.
_OLD_VALUE = "pilot_app_or_copilot_a[["
_NEW_VALUE = "pilot_app_or_copilot_app"


def fix_existing_rows(apps, schema_editor):
    ContestTeam = apps.get_model("display", "ContestTeam")
    Contestant = apps.get_model("display", "Contestant")

    contest_team_count = ContestTeam.objects.filter(tracking_device=_OLD_VALUE).update(tracking_device=_NEW_VALUE)
    contestant_count = Contestant.objects.filter(tracking_device=_OLD_VALUE).update(tracking_device=_NEW_VALUE)
    if contest_team_count or contestant_count:
        print(
            f"\n  Fixed {contest_team_count} ContestTeam and {contestant_count} Contestant row(s) "
            f"that held the corrupted TRACKING_PILOT_AND_COPILOT value."
        )


def revert_existing_rows(apps, schema_editor):
    ContestTeam = apps.get_model("display", "ContestTeam")
    Contestant = apps.get_model("display", "Contestant")

    ContestTeam.objects.filter(tracking_device=_NEW_VALUE).update(tracking_device=_OLD_VALUE)
    Contestant.objects.filter(tracking_device=_NEW_VALUE).update(tracking_device=_OLD_VALUE)


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0178_aeroplane_registration_club_name_unique"),
    ]

    operations = [
        migrations.RunPython(fix_existing_rows, revert_existing_rows),
        migrations.AlterField(
            model_name="contestteam",
            name="tracking_device",
            field=models.CharField(
                choices=[
                    ("device", "Hardware GPS tracker"),
                    ("pilot_app", "Pilot's Air Sports Live Tracking app"),
                    ("copilot_app", "Copilot's Air Sports Live Tracking app"),
                    ("pilot_app_or_copilot_app", "Pilot's or copilot's Air Sports Live Tracking app"),
                ],
                default="pilot_app_or_copilot_app",
                help_text="The device used for tracking the team",
                max_length=30,
            ),
        ),
        migrations.AlterField(
            model_name="contestant",
            name="tracking_device",
            field=models.CharField(
                choices=[
                    ("device", "Hardware GPS tracker"),
                    ("pilot_app", "Pilot's Air Sports Live Tracking app"),
                    ("copilot_app", "Copilot's Air Sports Live Tracking app"),
                    ("pilot_app_or_copilot_app", "Pilot's or copilot's Air Sports Live Tracking app"),
                ],
                default="pilot_app_or_copilot_app",
                help_text="The device used for tracking the team",
                max_length=30,
            ),
        ),
    ]
