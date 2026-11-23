"""
Warns before the turboSMTP plan that carries all outgoing e-mail runs out.

The plan is a prepaid package (50 000 e-mails valid for a year). When it expires, or is used up, the relay
refuses every message with "566 SMTP limit exceeded" and nothing reaches the pilots. turboSMTP's own alert only
looks at the share of credits used, which a year's plan never reaches here, so the expiry date is watched from here.

The SMTP username and password are a turboSMTP consumer key and secret, and they are accepted by the management
API as well.
"""

import datetime
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

PLANS_URL = "https://pro.api.serversmtp.com/api/v2/user/plans"
# Days before the expiry on which a warning e-mail is sent
EXPIRY_WARNING_DAYS = (14, 7, 3, 2, 1, 0)
# Share of the credits left under which a warning is sent
LOW_CREDIT_FRACTION = 0.1
LOW_CREDIT_REMINDER_SECONDS = 7 * 24 * 3600
LOW_CREDIT_CACHE_KEY = "smtp_low_credit_warning_sent"


@dataclass
class SmtpPlanStatus:
    limit: int
    sent: int
    expiration: datetime.date

    @property
    def remaining(self) -> int:
        return max(self.limit - self.sent, 0)

    def days_left(self, today: datetime.date) -> int:
        return (self.expiration - today).days


def is_configured() -> bool:
    return "turbo-smtp" in (settings.EMAIL_HOST or "")


def fetch_active_plan() -> Optional[SmtpPlanStatus]:
    """The plan e-mail is currently sent on, or None when no plan is active (nothing can be sent)"""
    response = requests.get(
        PLANS_URL,
        headers={"consumerKey": settings.EMAIL_HOST_USER, "consumerSecret": settings.EMAIL_HOST_PASSWORD},
        timeout=30,
    )
    response.raise_for_status()
    active = [plan for plan in response.json() if plan.get("active") and not plan.get("expired")]
    if not active:
        return None
    # With several active plans the one that lasts longest decides when sending stops
    plan = max(active, key=lambda plan: plan["plan_expiration"])
    return SmtpPlanStatus(
        limit=int(plan["smtp_limit"]),
        sent=int(plan["smtp_count"]),
        expiration=datetime.date.fromisoformat(plan["plan_expiration"][:10]),
    )


def warnings_for(plan: Optional[SmtpPlanStatus], today: datetime.date) -> list[str]:
    """What is worth telling the administrator about today, an empty list when all is well"""
    if plan is None:
        return ["There is no active turboSMTP plan: no e-mail is being sent."]
    warnings = []
    days_left = plan.days_left(today)
    if days_left in EXPIRY_WARNING_DAYS:
        warnings.append(f"The turboSMTP plan expires on {plan.expiration} ({days_left} days from now).")
    if plan.remaining < plan.limit * LOW_CREDIT_FRACTION and cache.add(
        LOW_CREDIT_CACHE_KEY, True, LOW_CREDIT_REMINDER_SECONDS
    ):
        warnings.append(f"Only {plan.remaining} of {plan.limit} turboSMTP e-mail credits are left.")
    return warnings


def check_smtp_credits(today: Optional[datetime.date] = None) -> list[str]:
    if not is_configured():
        return []
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    plan = fetch_active_plan()
    warnings = warnings_for(plan, today)
    if not warnings:
        return []
    message = " ".join(warnings)
    if plan is None:
        # E-mail is dead, so the error log (Sentry) is the only way out
        logger.error(message)
        return warnings
    logger.warning(message)
    send_mail(
        "Air Sports Live Tracking: the e-mail plan needs renewing",
        f"{message}\n\n"
        f"Used {plan.sent} of {plan.limit} e-mails, valid until {plan.expiration}.\n"
        "When the plan expires or is used up no e-mail reaches the pilots (flight orders, invitations).\n\n"
        "Renew it at https://dashboard.serversmtp.com/",
        None,
        recipient_list=[settings.SMTP_CREDIT_WARNING_EMAIL],
    )
    return warnings
