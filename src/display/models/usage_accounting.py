from django.conf import settings
from django.db import models


class ContestUsageLedger(models.Model):
    CONTEST_PILOT_STARTED = "contest_pilot_started"
    TASK_PILOT_STARTED = "task_pilot_started"
    KINDS = (
        (CONTEST_PILOT_STARTED, "Contest pilot started"),
        (TASK_PILOT_STARTED, "Task pilot started"),
    )

    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    navigation_task = models.ForeignKey("NavigationTask", null=True, blank=True, on_delete=models.SET_NULL)
    contestant = models.ForeignKey("Contestant", null=True, blank=True, on_delete=models.SET_NULL)
    team = models.ForeignKey("Team", null=True, blank=True, on_delete=models.SET_NULL)
    pilot = models.ForeignKey("Person", null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=40, choices=KINDS)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("contest", "pilot", "kind"),
                condition=models.Q(kind="contest_pilot_started"),
                name="unique_contest_pilot_started_usage",
            ),
            models.UniqueConstraint(
                fields=("contest", "navigation_task", "pilot", "kind"),
                condition=models.Q(kind="task_pilot_started"),
                name="unique_task_pilot_started_usage",
            ),
        ]

    def __str__(self):
        return f"{self.kind} for contest {self.contest_id}"
