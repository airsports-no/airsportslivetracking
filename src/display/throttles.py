from rest_framework.throttling import UserRateThrottle


class PeopleSearchThrottle(UserRateThrottle):
    """Per-user cap on type-ahead people searches; the rate is DEFAULT_THROTTLE_RATES["people_search"]."""

    scope = "people_search"
