from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotFound
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_vary_headers
import logging

logger = logging.getLogger(__name__)


class CDNSafetyMiddleware:
    """
    Ensures that the API is CDN-safe by:
    1. Forcing 'Vary: Authorization, Cookie' on all API responses.
    2. Defaulting non-cache-controlled API responses to 'private'.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only apply to API endpoints
        if request.path.startswith('/api/'):
            # 1. Ensure the CDN knows the response depends on auth state
            patch_vary_headers(response, ('Authorization', 'Cookie'))

            # 2. If no Cache-Control is set, default to private to be safe
            if 'Cache-Control' not in response:
                response['Cache-Control'] = 'private, no-cache'

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
