import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from live_tracking_map.settings import MBTILES_SERVER_URL


def get_available_maps() -> dict:
    try:
        result = _requests_retry_session().get(f"{MBTILES_SERVER_URL}services/")
        return result.json()
    except requests.exceptions.JSONDecodeError:
        return {}


def get_map_details(map_key: str) -> dict:
    try:
        result = _requests_retry_session().get(f"{MBTILES_SERVER_URL}services/{map_key}")
        return result.json()
    except requests.exceptions.JSONDecodeError:
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
