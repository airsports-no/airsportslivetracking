from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from display.models import MobileDevice
from display.services.push_notifications import _send_one


class Command(BaseCommand):
    help = (
        "Sends a test push notification to every phone registered for a person (by email), to check the whole chain "
        "from the backend through Firebase to the phone. Sends even when PUSH_NOTIFICATIONS_ENABLED is off, because "
        "somebody asked for exactly this person, and says so."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help="The person's email address (any case).")
        parser.add_argument("--title", default="Airsports test", help="Notification title.")
        parser.add_argument("--body", default="This is a test notification from Airsports.", help="Notification text.")

    def handle(self, *args, email, title, body, **options):
        devices = list(MobileDevice.objects.filter(person__email__iexact=email.strip()).select_related("person"))
        if not devices:
            raise CommandError(
                f"No phone is registered for {email}. Sign in on the phone with the app and allow notifications first."
            )
        if not settings.PUSH_NOTIFICATIONS_ENABLED:
            self.stdout.write(
                self.style.WARNING(
                    "PUSH_NOTIFICATIONS_ENABLED is off, so the automatic reminders are not being sent; this test is sent anyway."
                )
            )
        reached = 0
        for device in devices:
            label = f"{device.platform} app {device.app_version or '?'} (last seen {device.last_seen:%Y-%m-%d %H:%M} UTC)"
            try:
                if _send_one(device, title, body, {"type": "test"}):
                    reached += 1
                    self.stdout.write(self.style.SUCCESS(f"Sent to {label}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Firebase reports the token is no longer valid; deleted: {label}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed for {label}: {e}"))
        if not reached:
            raise CommandError("No phone was reached.")
        self.stdout.write(f"Reached {reached} of {len(devices)} phone(s).")
