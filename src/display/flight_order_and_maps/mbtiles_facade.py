import hashlib

import requests
from django.core.cache import cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from live_tracking_map.settings import MBTILES_SERVER_URL

AVAILABLE_MAPS_CACHE_TIMEOUT = 5
MAP_DETAILS_CACHE_TIMEOUT = 600


def get_available_maps() -> dict:
    cache_key = "mbtiles:available_maps"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _requests_retry_session().get(f"{MBTILES_SERVER_URL}services/")
        payload = result.json()
        cache.set(cache_key, payload, AVAILABLE_MAPS_CACHE_TIMEOUT)
        return payload
    except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError):
        return {}


def get_map_details(map_key: str) -> dict:
    cache_key = f"mbtiles:map_details:{hashlib.sha256(map_key.encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        result = _requests_retry_session().get(f"{MBTILES_SERVER_URL}services/{map_key}")
        payload = result.json()
        cache.set(cache_key, payload, MAP_DETAILS_CACHE_TIMEOUT)
        return payload
    except (requests.exceptions.RequestException, requests.exceptions.JSONDecodeError):
        return {}


def _requests_retry_session(
    retries=10,
    backoff_factor=0.5,
    status_forcelist=(502,),
    session=None,
):
    """
    Request with retry. Borrowed from https://www.peterbe.com/plog/best-practice-with-retries-with-requests
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
