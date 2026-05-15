import logging

class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Filter out health check logs
        return "/display/healthz/" not in record.getMessage()
