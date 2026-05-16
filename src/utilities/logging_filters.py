import logging

class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Filter out health check logs from various loggers (Django, Daphne, Uvicorn)
        # These typically contain the request path in the message.
        msg = record.getMessage()
        return "/healthz/" not in msg and "/readyz/" not in msg
