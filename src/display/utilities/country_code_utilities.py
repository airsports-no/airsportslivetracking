import logging

from django.conf import settings
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Returned instead of a live reverse-geocode lookup while running the test suite.
UNIT_TESTING_COUNTRY_CODE = "no"


class CountryNotFoundException(Exception):
    pass


def get_country_code_from_location(latitude: float, longitude: float):
    if settings.IS_UNIT_TESTING:
        # Contest creation reverse-geocodes through Nominatim, which is rate limited to
        # roughly one request per second and is the slowest and flakiest thing in the
        # suite. No test asserts on the resolved country.
        return UNIT_TESTING_COUNTRY_CODE
    try:
        geolocator = Nominatim(user_agent="airsports.no")
        location = geolocator.reverse(f"{latitude}, {longitude}")
        return location.raw["address"]["country_code"]
    except (AttributeError, KeyError) as e:
        logger.warning(f"Failed fetching country for location {latitude}, {longitude}")
        raise CountryNotFoundException(e)
    except:
        logger.warning(f"Unexpected error when failed fetching country for location {latitude}, {longitude}")
        raise
