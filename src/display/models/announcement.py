from django.conf import settings
from django.db import models


class ContestAnnouncement(models.Model):
    """
    A message from the organizers to the pilots of a contest (or of one task in it). It is sent as a push notification to
    the phones of the crews and listed in the mobile app until it expires.
    """

    contest = models.ForeignKey("Contest", on_delete=models.CASCADE, related_name="announcements")
    navigation_task = models.ForeignKey(
        "NavigationTask",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Limits the announcement to the crews of this task. Empty: every crew registered in the contest.",
    )
    message = models.CharField(max_length=500)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    people_reached = models.PositiveIntegerField(default=0, help_text="How many people got the push notification.")

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.contest}: {self.message[:40]}"
