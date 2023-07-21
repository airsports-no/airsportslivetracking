import logging

from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)


class CountryNotFoundException(Exception):
    pass


def get_country_code_from_location(latitude: float, longitude: float):
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
