import requests
from requests import Response
from typing import Dict

WORDPRESS_ROOT = "https://home.airsports.no"
API_PATH = "/wp-json/wp/v2/"

WELCOME_EMAIL_PAGE = 111
CONTEST_CREATION_EMAIL_PAGE = 113
EMAIL_SIGNATURE_PAGE = 115


def _get(path: str) -> Response:
    return requests.get(f"{WORDPRESS_ROOT}{API_PATH}{path}")


def get_page(id: int) -> Dict:
    return _get(f"pages/{id}/").json()
