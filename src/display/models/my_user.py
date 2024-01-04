import logging
import typing

import html2text
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django_use_email_as_username.models import BaseUser, BaseUserManager
from guardian.mixins import GuardianUserMixin

from display.utilities.welcome_emails import render_welcome_email, render_contest_creation_email, render_deletion_email
from live_tracking_map.settings import SUPPORT_EMAIL

if typing.TYPE_CHECKING:
    from display.models import Person

logger = logging.getLogger(__name__)


class MyUser(BaseUser, GuardianUserMixin):
    """
    Typical custom Django user model.
    """
    username = models.CharField(max_length=50, default="not_applicable")
    objects = BaseUserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def person(self) -> "Person":
        from display.models import Person

        return Person.objects.get(email=self.email)

    def send_welcome_email(self, person: "Person"):
        try:
            html = render_welcome_email(person)
            if len(html) == 0:
                raise Exception("Did not receive any text for welcome email")
        except:
            logger.exception("Failed to generate welcome email, fall back to earlier implementation.")
            html = render_to_string("display/welcome_email.html", {"person": person})
        converter = html2text.HTML2Text()
        plaintext = converter.handle(html)
        try:
            send_mail(
                f"Welcome to Air Sports Live Tracking",
                plaintext,
                None,  # Should default to system from email
                recipient_list=[self.email, SUPPORT_EMAIL],
                html_message=html,
            )
        except:
            logger.exception(f"Failed sending email to {self}")

    def send_contest_creator_email(self, person: "Person"):
        try:
            html = render_contest_creation_email(person)
            if len(html) == 0:
                raise Exception("Did not receive any text for welcome email")
        except:
            logger.exception("Failed to generate contest creation email, fall back to earlier implementation.")
            html = render_to_string("display/contestmanagement_email.html", {"person": person})
        converter = html2text.HTML2Text()
        plaintext = converter.handle(html)
        logger.debug(f"Sending contest creation email to {person}")
        try:
            send_mail(
                f"You have been granted contest creation privileges at Air Sports Live Tracking",
                plaintext,
                None,  # Should default to system from email
                recipient_list=[self.email, SUPPORT_EMAIL],
                html_message=html,
            )
        except:
            logger.exception(f"Failed sending email to {self}")

    def send_deletion_email(self):
        try:
            html = render_deletion_email()
            if len(html) == 0:
                raise Exception("Did not receive any text for deletion email")
            converter = html2text.HTML2Text()
            plaintext = converter.handle(html)
            logger.debug(f"Sending user deletion email to {self.email}")
            try:
                send_mail(
                    f"Your user profile has been deleted from Air Sports Live Tracking",
                    plaintext,
                    None,  # Should default to system from email
                    recipient_list=[self.email, SUPPORT_EMAIL],
                    html_message=html,
                )
            except:
                logger.exception(f"Failed sending email to {self}")
        except:
            logger.exception("Failed to generate user deletion email, you need to send it manually")
            raise
