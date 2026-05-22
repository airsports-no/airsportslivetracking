from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotFound
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_vary_headers
import logging

logger = logging.getLogger(__name__)


class CDNSafetyMiddleware:
    """
    Ensures that the API is CDN-safe by:
    1. Defaulting non-cache-controlled API responses to 'private'.
    2. Adding 'Vary: Authorization, Cookie' on responses that are not
       explicitly marked public, so per-user content does not leak through
       the shared CDN cache.
    3. Forcing 'no-store' on auth-error responses (400/401/403) so the CDN
       does not negative-cache an auth failure.

    Vary is intentionally NOT added to public responses: a 'Vary: Cookie'
    header on a publicly-cacheable endpoint causes the CDN to fragment the
    cache by cookie, defeating the cache and leaving every spectator hitting
    the origin.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only apply to API endpoints
        if not request.path.startswith('/api/'):
            return response

        # 1. Default to private for any endpoint that did not set Cache-Control.
        if 'Cache-Control' not in response:
            response['Cache-Control'] = 'private, no-cache'

        # 2. Auth-error responses must not be cached anywhere.
        if response.status_code in (400, 401, 403):
            response['Cache-Control'] = 'no-store, private'

        # 3. Handle Vary header based on cache-control
        cache_control = response.get('Cache-Control', '').lower()
        if 'public' in cache_control:
            # Public responses must stay cookie-agnostic to be cache-effective.
            # If some other middleware (like SessionMiddleware) added 'Cookie' to Vary,
            # we must remove it.
            if response.has_header('Vary'):
                vary_values = [v.strip() for v in response['Vary'].split(',')]
                # We want to keep other Vary headers if any, but exclude Cookie and Authorization
                new_vary = [v for v in vary_values if v.lower() not in ('cookie', 'authorization')]
                if new_vary:
                    response['Vary'] = ', '.join(new_vary)
                else:
                    del response['Vary']
        else:
            # Non-public responses should Vary on auth/cookie to prevent leakage.
            patch_vary_headers(response, ('Authorization', 'Cookie'))

        return response


class HandleKnownExceptionsMiddleware(MiddlewareMixin):
    """
    Catches known exceptions and returns the proper response code to the client
    """

    def process_exception(self, request, exception):
        # if isinstance(exception, jsonschema.exceptions.ValidationError):
        #     return HttpResponseBadRequest(exception.message)
        if isinstance(exception, ValueError):
            return HttpResponseBadRequest("ValueError: {}".format(exception))
        # if isinstance(exception, Http404):
        #     return HttpResponseNotFound(str(exception))


class FirebaseSessionMiddleware:
    """
    Exchanges Firebase ID Tokens (set by authentication backends) 
    for long-lived Firebase Session Cookies.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # If the auth backend attached an ID token, exchange it for a session cookie
        if hasattr(request, "_firebase_id_token"):
            try:
                from datetime import timedelta
                from firebase_admin import auth
                from django.conf import settings
                from display.auth_backends import FirebaseMigrationBackend

                # Ensure Firebase is initialized
                FirebaseMigrationBackend()._initialize_firebase()

                # Set session expiration to match Django's (default 30 days)
                expires_in = timedelta(seconds=getattr(settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 30))
                
                # Firebase session cookie max is 2 weeks. Cap it.
                if expires_in > timedelta(days=14):
                    expires_in = timedelta(days=14)

                session_cookie = auth.create_session_cookie(
                    request._firebase_id_token, 
                    expires_in=expires_in
                )
                
                # Set the cookie on the response
                response.set_cookie(
                    "session", # Firebase default cookie name
                    session_cookie,
                    max_age=int(expires_in.total_seconds()),
                    httponly=True,
                    secure=not getattr(settings, "DEBUG", False),
                    samesite="Lax"
                )
                logger.info(f"Firebase Session Cookie created for user {request.user}")
            except Exception as e:
                logger.error(f"Failed to create Firebase Session Cookie: {e}")

        return response


# Exceptions that Django turns into non-500 responses — logging them as 500s
# floods the error monitor with noise (see issue #100).
_NON_500_EXCEPTIONS = (Http404, PermissionDenied)


class Log500ErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, _NON_500_EXCEPTIONS):
            return None
        exc_info = (type(exception), exception, exception.__traceback__)
        logger.error("Intercepted 500 error", exc_info=exc_info)
        return None  # Let other middlewares do further processing
