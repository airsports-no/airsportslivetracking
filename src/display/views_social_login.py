"""
Sign in with Google or Apple on the website.

The browser signs in with the provider through the Firebase web SDK (react_vite/src/SocialLogin.tsx), exactly like the
app does, and posts the resulting Firebase ID token here. The token is verified like the apps' token
(display.authentication.FirebaseTokenAuthentication, which also provisions a first-time user) and the ordinary Django
session is started, so everything after the login is the same as after the email/password form.
"""

import base64
import hashlib
import json
import logging
import re
import secrets
from functools import wraps
from typing import Optional

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
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


# ---- Sign-in for the MSFS client (Windows) ------------------------------------------------------------------------
#
# A desktop app cannot show the providers' sign-in itself (Google refuses embedded browsers, Apple only returns to
# registered https addresses), so it borrows the website's, the usual way for desktop apps (RFC 8252):
#   1. The client listens on a free port on 127.0.0.1 and opens desktop_sign_in in the browser with that port, a random
#      state and the SHA-256 of a secret it keeps (code_challenge, as in OAuth PKCE).
#   2. The person signs in with Google or Apple on that page (SocialLogin.tsx, as on the login page), and
#      desktop_sign_in_complete sends the browser back to http://127.0.0.1:<port>/callback with a one-time code.
#   3. The client trades the code and its secret for a Firebase custom token (desktop_sign_in_token) and signs in to
#      Firebase with it: the same Firebase user as on the website and in the apps.
# The code is useless without the secret, which never leaves the client, and it works once, for a short while.

DESKTOP_CODE_SECONDS = 120
_STATE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43}$")
_PROVIDERS = {"google", "apple"}


def _desktop_parameters(params) -> tuple[Optional[dict], Optional[str]]:
    """The client's port, state, code challenge and (optional) provider, or an error text."""
    try:
        port = int(params.get("port", ""))
    except ValueError:
        port = 0
    state = params.get("state", "")
    challenge = params.get("code_challenge", "")
    provider = params.get("provider", "")
    if not 1024 <= port <= 65535 or not _STATE.match(state) or not _CHALLENGE.match(challenge):
        return None, "This sign-in link is not valid."
    if provider and provider not in _PROVIDERS:
        return None, "This sign-in link is not valid."
    return {"port": port, "state": state, "code_challenge": challenge, "provider": provider}, None


def _desktop_code_key(code: str) -> str:
    return f"desktop_sign_in:{hashlib.sha256(code.encode()).hexdigest()}"


@require_GET
@ensure_csrf_cookie
@allow_auth_popups
def desktop_sign_in(request):
    """The page the client opens in the browser: the Google / Apple buttons, finishing in desktop_sign_in_complete."""
    context = social_login_context()
    parameters, error = _desktop_parameters(request.GET)
    if error:
        return render(request, "registration/desktop_sign_in.html", {**context, "error": error}, status=400)
    query = "&".join(f"{key}={parameters[key]}" for key in ("port", "state", "code_challenge"))
    context.update(
        {"complete_endpoint": f"{reverse('desktop_sign_in_complete')}?{query}", "provider": parameters["provider"]}
    )
    return render(request, "registration/desktop_sign_in.html", context)


@require_POST
def desktop_sign_in_complete(request):
    """
    POST {"id_token": <Firebase ID token>} from the desktop sign-in page, with the client's port, state and challenge in
    the query. Answers {"redirect": "http://127.0.0.1:<port>/callback?code=..&state=.."}, or {"error": ...} like
    firebase_web_login. No session is started: the sign-in is for the client, not for this browser.
    """
    if not getattr(settings, "SOCIAL_LOGIN_ENABLED", False):
        return JsonResponse({"error": "Sign-in with Google or Apple is not enabled."}, status=404)
    parameters, error = _desktop_parameters(request.GET)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "Invalid request."}, status=400)
    id_token = payload.get("id_token") if isinstance(payload, dict) else None
    if not id_token or not isinstance(id_token, str):
        return JsonResponse({"error": "Missing sign-in token."}, status=400)

    from display.authentication import FirebaseTokenAuthentication

    try:
        user, decoded_token = FirebaseTokenAuthentication().authenticate_credentials(id_token)
    except drf_exceptions.AuthenticationFailed as e:
        cause = e.__context__ or e
        logger.warning("Desktop sign-in with a Firebase token failed: %s: %s", type(cause).__name__, cause)
        return JsonResponse({"error": "We could not verify your sign-in. Please try again."}, status=401)
    _ensure_person(user)
    code = secrets.token_urlsafe(32)
    cache.set(
        _desktop_code_key(code),
        {"uid": decoded_token["uid"], "code_challenge": parameters["code_challenge"]},
        DESKTOP_CODE_SECONDS,
    )
    redirect = f"http://127.0.0.1:{parameters['port']}/callback?code={code}&state={parameters['state']}"
    return JsonResponse({"redirect": redirect})


@csrf_exempt
@require_POST
def desktop_sign_in_token(request):
    """
    POST {"code": <from the callback>, "code_verifier": <the client's secret>} from the client. Answers
    {"custom_token": <Firebase custom token>} once per code, or {"error": ...} with 400.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "Invalid request."}, status=400)
    code = payload.get("code") if isinstance(payload, dict) else None
    verifier = payload.get("code_verifier") if isinstance(payload, dict) else None
    if not isinstance(code, str) or not isinstance(verifier, str) or not code or not verifier:
        return JsonResponse({"error": "Invalid request."}, status=400)
    key = _desktop_code_key(code)
    entry = cache.get(key)
    cache.delete(key)  # once, whatever happens next
    if not entry:
        return JsonResponse({"error": "The sign-in has expired. Please sign in again."}, status=400)
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    if not secrets.compare_digest(expected, entry["code_challenge"]):
        return JsonResponse({"error": "The sign-in could not be completed. Please sign in again."}, status=400)

    from firebase_admin import auth as firebase_auth

    from display.auth_backends import FirebaseMigrationBackend

    FirebaseMigrationBackend()._initialize_firebase()
    token = firebase_auth.create_custom_token(entry["uid"])
    return JsonResponse({"custom_token": token.decode() if isinstance(token, bytes) else token})


@require_GET
def desktop_sign_in_done(request):
    """Where the client sends the browser when it has the code: tells the person to go back to the client."""
    return render(request, "registration/desktop_sign_in_done.html")
