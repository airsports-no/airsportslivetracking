"""The e-mail that tells somebody they have been invited to a squadron."""

import logging

import html2text
from django.core.mail import send_mail
from django.template import Context, Template

from display.models import SquadronInvitation, SquadronMembership
from display.utilities.email_templates import EMAIL_SIGNATURE, SQUADRON_INVITATION_EMAIL
from display.utilities.welcome_emails import FOOTER, HEADER

logger = logging.getLogger(__name__)

APP_URL = "https://app.airsports.no"
SQUADRONS_PATH = "/squadrons"


def _inviter_name(invitation: SquadronInvitation) -> str:
    user = invitation.invited_by
    name = f"{user.first_name} {user.last_name}".strip() if user else ""
    return name or "An admin of the squadron"


def send_squadron_invitation_email(invitation: SquadronInvitation) -> bool:
    """
    Mail the invitation to the address it is for. Nothing is sent for an invitation that is no longer open, so a late
    delivery after it was answered or cancelled does no harm. Returns whether a mail was sent.
    """
    if invitation.status != SquadronInvitation.PENDING:
        return False
    squadron = invitation.squadron
    inviter = _inviter_name(invitation)
    # Squadron name, description and names are user-controlled; Template autoescapes them in the HTML body
    html = Template(HEADER + SQUADRON_INVITATION_EMAIL + EMAIL_SIGNATURE + FOOTER).render(
        Context(
            {
                "squadron": squadron.name,
                "description": squadron.description,
                "inviter": inviter,
                "admin": invitation.role == SquadronMembership.ADMIN,
                "email": invitation.email,
                "url": APP_URL + SQUADRONS_PATH,
            }
        )
    )
    converter = html2text.HTML2Text()
    converter.ignore_images = True
    send_mail(
        f"{inviter} invited you to the squadron {squadron.name}",
        converter.handle(html),
        None,  # Should default to system from email
        recipient_list=[invitation.email],
        html_message=html,
    )
    return True
