import logging

from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)


def get_country_code_from_location(latitude: float, longitude: float):
    try:
        geolocator = Nominatim(user_agent="airsports.no")
        location = geolocator.reverse(f"{latitude}, {longitude}")
        return location.raw["address"]["country_code"]
    except:
        logger.exception(
            f"Failed fetching country for location {latitude}, {longitude}"
        )
        return "xxx"
