import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("display", "0192_mobileappactivity"),
    ]

    operations = [
        migrations.CreateModel(
            name="SimulatorQuickstart",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "active",
                    models.BooleanField(
                        default=True, help_text="Only active quickstarts are offered; the newest active one wins."
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        blank=True, default="", help_text="Shown as the heading in the client. Empty: the task's name.", max_length=100
                    ),
                ),
                (
                    "description",
                    models.TextField(blank=True, default="", help_text="A few sentences about the flight, shown in the client."),
                ),
                (
                    "start_location",
                    models.CharField(
                        help_text="Where to start in the simulator, as the pilot finds it in the MSFS world map, e.g. 'Kjeller (ENKJ), runway 30'.",
                        max_length=200,
                    ),
                ),
                (
                    "start_instructions",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Anything else the pilot should do before the start, e.g. 'Take off and fly to the starting point at 1500 ft.'",
                    ),
                ),
                (
                    "air_start_altitude_ft",
                    models.PositiveIntegerField(
                        default=2500,
                        help_text="Altitude (feet above sea level) for the client's 'start in the air' option, 2 NM before the starting point.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "navigation_task",
                    models.ForeignKey(
                        help_text="Must allow self-management (pilots register themselves). An adaptive-start task with a long window suits a practice flight best.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="simulator_quickstarts",
                        to="display.navigationtask",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
