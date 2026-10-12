from django.db import models


class SimulatorQuickstart(models.Model):
    """
    A practice flight offered to new pilots in the MSFS client: a navigation task they can register for themselves, and
    where to start in the simulator. The client shows the newest active one on its Home page to pilots without a flight.
    """

    navigation_task = models.ForeignKey(
        "NavigationTask",
        on_delete=models.CASCADE,
        related_name="simulator_quickstarts",
        help_text="Must allow self-management (pilots register themselves). An adaptive-start task with a long window suits a practice flight best.",
    )
    active = models.BooleanField(default=True, help_text="Only active quickstarts are offered; the newest active one wins.")
    title = models.CharField(
        max_length=100, blank=True, default="", help_text="Shown as the heading in the client. Empty: the task's name."
    )
    description = models.TextField(blank=True, default="", help_text="A few sentences about the flight, shown in the client.")
    start_location = models.CharField(
        max_length=200,
        help_text="Where to start in the simulator, as the pilot finds it in the MSFS world map, e.g. 'Kjeller (ENKJ), runway 30'.",
    )
    start_instructions = models.TextField(
        blank=True,
        default="",
        help_text="Anything else the pilot should do before the start, e.g. 'Take off and fly to the starting point at 1500 ft.'",
    )
    air_start_altitude_ft = models.PositiveIntegerField(
        default=2500,
        help_text="Altitude (feet above sea level) for the client's 'start in the air' option, 2 NM before the starting point.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title or self.navigation_task.name} ({'active' if self.active else 'inactive'})"
