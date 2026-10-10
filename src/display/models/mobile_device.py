import hashlib
import logging

from django.db import models

from display.models.team_structure import Person

logger = logging.getLogger(__name__)

PLATFORM_ANDROID = "android"
PLATFORM_IOS = "ios"
MOBILE_PLATFORMS = ((PLATFORM_ANDROID, "Android"), (PLATFORM_IOS, "iOS"))


class MobileDevice(models.Model):
    """
    A phone running the Airsports app that can receive push notifications (FCM token). A token belongs to one
    person at a time: when someone else signs in on the same phone the token moves to them.
    """

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="mobile_devices")
    platform = models.CharField(max_length=10, choices=MOBILE_PLATFORMS)
    push_token = models.CharField(max_length=512)
    # Uniqueness is enforced on a digest because MySQL cannot reliably index a unique 512-character column.
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    app_version = models.CharField(max_length=40, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        self.token_hash = self.hash_token(self.push_token)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.person} ({self.platform})"


class PushNotificationLog(models.Model):
    """Records what was sent so periodic jobs never notify the same person twice about the same thing."""

    KIND_TRACKING_WINDOW_OPENS = "tracking_window_opens"
    KIND_NOT_TRACKING = "not_tracking"
    KINDS = (
        (KIND_TRACKING_WINDOW_OPENS, "Tracking window opens soon"),
        (KIND_NOT_TRACKING, "Flight started but no positions received"),
    )

    kind = models.CharField(max_length=40, choices=KINDS)
    contestant = models.ForeignKey("display.Contestant", on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    devices_reached = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "contestant", "person"], name="unique_push_per_contestant_person")
        ]
