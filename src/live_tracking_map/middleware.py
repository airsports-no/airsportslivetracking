from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotFound
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


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
