"""
Sign in with Google or Apple on the website.

The browser signs in with the provider through the Firebase web SDK (react_vite/src/SocialLogin.tsx), exactly like the
app does, and posts the resulting Firebase ID token here. The token is verified like the apps' token
(display.authentication.FirebaseTokenAuthentication, which also provisions a first-time user) and the ordinary Django
session is started, so everything after the login is the same as after the email/password form.
"""

import json
import logging
from functools import wraps

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from rest_framework import exceptions as drf_exceptions

logger = logging.getLogger(__name__)

# The provider's sign-in window is a popup that has to talk back to the page. The site's default
# "same-origin" would cut that link (the popup is then reported as closed), "same-origin-allow-popups" keeps it.
POPUP_FRIENDLY_OPENER_POLICY = "same-origin-allow-popups"


def social_login_context() -> dict:
    """Template context for the sign in buttons. Empty (no buttons) when social login is switched off."""
    if not getattr(settings, "SOCIAL_LOGIN_ENABLED", False):
        return {"social_login_enabled": False}
    return {"social_login_enabled": True, "firebase_web_config": settings.FIREBASE_WEB_CONFIG}


def allow_auth_popups(view):
    """Lets the provider's sign-in popup talk to the page, for the pages that have the sign in buttons."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if getattr(settings, "SOCIAL_LOGIN_ENABLED", False):
            response["Cross-Origin-Opener-Policy"] = POPUP_FRIENDLY_OPENER_POLICY
        return response

    return wrapped


class SocialLoginAwareLoginView(LoginView):
    """The ordinary login page, with the Google and Apple buttons."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(social_login_context())
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if getattr(settings, "SOCIAL_LOGIN_ENABLED", False):
            response["Cross-Origin-Opener-Policy"] = POPUP_FRIENDLY_OPENER_POLICY
        return response


def _safe_next(request, next_url: str) -> str:
    if (
        next_url
        and next_url.startswith("/")
        and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        )
    ):
        return next_url
    return settings.LOGIN_REDIRECT_URL


def _ensure_person(user) -> None:
    """
    A first-time user created by the token authentication has no Person yet, and pages that look at the person of
    the signed-in user would fail until something else creates it (the app does, with its first profile request).
    Mirrors that creation. Never blocks the sign-in: creating a Person registers a tracker with Traccar, and the
    profile is created on its first use anyway if this fails.
    """
    from display.models import Person

    try:
        Person.objects.get_or_create(
            email=user.email,
            defaults={"first_name": user.first_name or "", "last_name": user.last_name or ""},
        )
    except Exception:
        logger.exception("Could not create the person profile for %s at website sign-in", user.email)


@require_POST
def firebase_web_login(request):
    """
    POST {"id_token": <Firebase ID token>, "next": <path>}. Starts the session and answers {"redirect": <path>}, or
    {"error": <text>} with 400 (bad request) / 401 (the token or the account is not accepted).
    """
    if not getattr(settings, "SOCIAL_LOGIN_ENABLED", False):
        return JsonResponse({"error": "Sign-in with Google or Apple is not enabled."}, status=404)
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "Invalid request."}, status=400)
    id_token = payload.get("id_token") if isinstance(payload, dict) else None
    if not id_token or not isinstance(id_token, str):
        return JsonResponse({"error": "Missing sign-in token."}, status=400)

    from display.authentication import FirebaseTokenAuthentication

    try:
        user, _decoded_token = FirebaseTokenAuthentication().authenticate_credentials(id_token)
    except drf_exceptions.AuthenticationFailed as e:
        # authenticate_credentials wraps whatever went wrong, so the original exception is the one it was raised from
        cause = e.__context__ or e
        logger.warning(
            "Website sign-in with a Firebase token failed: %s: %s", type(cause).__name__, cause, exc_info=settings.DEBUG
        )
        body = {"error": "We could not verify your sign-in. Please try again."}
        if settings.DEBUG:
            body["detail"] = f"{type(cause).__name__}: {cause}"  # for developers only
        return JsonResponse(body, status=401)
    _ensure_person(user)
    # The backend recorded in the session must be listed in settings.AUTHENTICATION_BACKENDS (see firebase_token_login)
    login(request, user, backend="display.auth_backends.FirebaseMigrationBackend")
    return JsonResponse({"redirect": _safe_next(request, payload.get("next") or "")})
