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

        if not request.path.startswith('/api/'):
            return response

        # Default to private for any endpoint that did not set Cache-Control.
        if 'Cache-Control' not in response:
            response['Cache-Control'] = 'private, no-cache'

        # Auth-error responses must not be cached anywhere.
        if response.status_code in (400, 401, 403):
            response['Cache-Control'] = 'no-store, private'

        # Only fragment the cache by cookie/auth for non-public responses.
        # Public responses must stay cookie-agnostic to be cache-effective.
        cache_control = response.get('Cache-Control', '')
        if 'public' not in cache_control:
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
