from django.conf import settings
from django.db import models

from display.models.mobile_device import MOBILE_PLATFORMS


class MobileAppActivity(models.Model):
    """
    The last time a signed-in user's Airsports app talked to the server, and which version it was. Written at most once a
    minute per user and platform (see display.services.mobile_app_activity); feeds the admin "Mobile apps" statistics.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobile_app_activity")
    platform = models.CharField(max_length=10, choices=MOBILE_PLATFORMS)
    app_version = models.CharField(max_length=40, blank=True, default="", help_text="The version name, e.g. 2.0.0.")
    app_build = models.CharField(max_length=20, blank=True, default="", help_text="Android versionCode / iOS build number.")
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField()

    class Meta:
        unique_together = ("user", "platform")
        ordering = ("-last_seen",)

    def __str__(self):
        return f"{self.user} ({self.platform} {self.app_version} {self.app_build})"
