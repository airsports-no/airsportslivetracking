from django.conf import settings
from django.db import models


class ContestUsageLedger(models.Model):
    CONTESTANT_STARTED = "contestant_started"
    TASK_STARTED = "task_started"
    KINDS = (
        (CONTESTANT_STARTED, "Contestant started"),
        (TASK_STARTED, "Task started"),
    )

    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    navigation_task = models.ForeignKey("NavigationTask", null=True, blank=True, on_delete=models.SET_NULL)
    contestant = models.ForeignKey("Contestant", null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=40, choices=KINDS)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("contest", "contestant", "kind"),
                condition=models.Q(kind="contestant_started"),
                name="unique_contestant_started_usage",
            ),
            models.UniqueConstraint(
                fields=("contest", "navigation_task", "kind"),
                condition=models.Q(kind="task_started"),
                name="unique_task_started_usage",
            ),
        ]

    def __str__(self):
        return f"{self.kind} for contest {self.contest_id}"
