from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("display", "0197_simulator_policy_and_flight_mode"),
    ]

    operations = [
        migrations.RemoveField(model_name="person", name="is_public"),
        migrations.RemoveField(model_name="person", name="last_seen"),
        migrations.AlterField(
            model_name="person",
            name="app_aircraft_registration",
            field=models.CharField(
                blank=True,
                default="",
                help_text="The callsign of the person's positions on the partner traffic feed when they are tracked without a contestant (should be an aircraft registration",
                max_length=100,
            ),
        ),
        migrations.AlterField(
            model_name="person",
            name="simulator_tracking_id",
            field=models.CharField(
                db_index=True,
                editable=False,
                help_text="An automatically generated tracking ID which is distributed to the simulator integration. Persons or contestants identified by this field are not sent on the partner traffic feed.",
                max_length=28,
            ),
        ),
    ]
