import logging
import uuid

from django.core.mail import send_mail
from django.db import models
from django.template import Context, Template
from django.urls import reverse

from display.utilities.email_templates import EMAIL_SIGNATURE, FLIGHT_ORDER_EMAIL, PLAIN_SIGNATURE
from display.utilities.welcome_emails import FOOTER, HEADER

logger = logging.getLogger(__name__)


class EmailMapLink(models.Model):
    """
    Contains a generated flight order for a contestant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    orders = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    @property
    def HTML_SIGNATURE(self):
        return EMAIL_SIGNATURE

    PLAINTEXT_SIGNATURE = PLAIN_SIGNATURE

    def __str__(self):
        return str(self.contestant) + " " + str(self.contestant.navigation_task)

    def get_absolute_url(self):
        return "https://app.airsports.no" + reverse("email_map_link", kwargs={"key": self.id})

    def send_email(self, email_address: str, first_name: str):
        """
        Sends an e-mail to a contestant with a link to the flight order.
        """
        logger.info(f"Sending email to {email_address}")
        url = "https://app.airsports.no" + reverse("email_map_link", kwargs={"key": self.id})

        navigation_task = self.contestant.navigation_task
        contest_name = navigation_task.contest.name
        # %Z labels the contest timezone so the time is unambiguous for pilots flying away from home
        starting_point_time_string = self.contestant.starting_point_time_local.strftime("%Y-%m-%d %H:%M:%S %Z")
        tracking_start_time_string = self.contestant.tracker_start_time_local.strftime("%Y-%m-%d %H:%M:%S %Z")
        time_kind = "estimated" if self.contestant.adaptive_start else "exact"
        adaptive = self.contestant.adaptive_start

        description = (
            f"{navigation_task.name} in {contest_name}, {time_kind} starting point time {starting_point_time_string}"
        )
        # Task, contest and first names are user-controlled; Template autoescapes them in the HTML body
        html = Template(HEADER + FLIGHT_ORDER_EMAIL).render(
            Context(
                {
                    "first_name": first_name,
                    "task": navigation_task.name,
                    "contest": contest_name,
                    "start_time": starting_point_time_string,
                    "time_kind": time_kind,
                    "adaptive": adaptive,
                    "tracking_start": tracking_start_time_string,
                    "url": url,
                }
            )
        )
        send_mail(
            f"Flight orders for task {navigation_task.name} ({contest_name})",
            f"Hi {first_name},\n\nHere are the flight orders for {description}.\n"
            f"Tracking window opens: {tracking_start_time_string}.\n\n"
            f"Open your flight orders: {url}\n\n"
            "On the day: open the app, run the pre-flight check and press play before take-off.\n"
            f"{self.PLAINTEXT_SIGNATURE}",
            None,  # Should default to system from email
            recipient_list=[email_address],
            html_message=html + self.HTML_SIGNATURE + FOOTER,
        )
