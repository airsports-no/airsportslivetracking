from django.http import HttpResponseBadRequest
from django.utils.deprecation import MiddlewareMixin


class HandleKnownExceptionsMiddleware(MiddlewareMixin):
    """
    Catches known exceptions and returns the proper response code to the client
    """
    def process_exception(self, request, exception):
        # if isinstance(exception, jsonschema.exceptions.ValidationError):
        #     return HttpResponseBadRequest(exception.message)
        if isinstance(exception, ValueError):
            return HttpResponseBadRequest("ValueError: {}".format(exception))
