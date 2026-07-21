from django.conf import settings
from django.db import models


class ContestUsageLedger(models.Model):
    CONTEST_TEAM_STARTED = "contest_team_started"
    TASK_TEAM_STARTED = "task_team_started"
    KINDS = (
        (CONTEST_TEAM_STARTED, "Contest team started"),
        (TASK_TEAM_STARTED, "Task team started"),
    )

    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    navigation_task = models.ForeignKey("NavigationTask", null=True, blank=True, on_delete=models.SET_NULL)
    contestant = models.ForeignKey("Contestant", null=True, blank=True, on_delete=models.SET_NULL)
    team = models.ForeignKey("Team", null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=40, choices=KINDS)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("contest", "team", "kind"),
                condition=models.Q(kind="contest_team_started"),
                name="unique_contest_team_started_usage",
            ),
            models.UniqueConstraint(
                fields=("contest", "navigation_task", "team", "kind"),
                condition=models.Q(kind="task_team_started"),
                name="unique_task_team_started_usage",
            ),
        ]

    def __str__(self):
        return f"{self.kind} for contest {self.contest_id}"
