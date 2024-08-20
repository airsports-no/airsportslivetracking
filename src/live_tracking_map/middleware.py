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


class Log500ErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        exc_info = (type(exception), exception, exception.__traceback__)
        logger.error("Intercepted 500 error", exc_info=exc_info)
        return None  # Let other middlewares do further processing
