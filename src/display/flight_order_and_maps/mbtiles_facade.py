import requests

from live_tracking_map.settings import MBTILES_SERVER_URL


def get_available_maps() -> dict:
    result = requests.get(f"{MBTILES_SERVER_URL}services/")
    return result.json()


def get_map_details(map_key: str) -> dict:
    result = requests.get(f"{MBTILES_SERVER_URL}services/{map_key}")
    return result.json()
