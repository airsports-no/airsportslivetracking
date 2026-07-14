from PIL import Image
import qrcode

from live_tracking_map.settings import MBTILES_PUBLIC_URL
from display.flight_order_and_maps.mbtiles_facade import get_available_maps, get_map_details

BUILTIN_NON_MBTILES_SOURCES = {
    "osm": {
        "label": "OSM",
        "type": "raster_xyz",
        "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "© OpenStreetMap contributors",
        "min_zoom": 0,
        "max_zoom": 19,
        "default_zoom": 12,
        "is_overlay": False,
    },
    "fc": {
        "label": "Flight Contest",
        "type": "raster_xyz",
        "tile_url": "https://flightcontest.de/route/maps/{z}/{x}/{y}.png",
        "attribution": "FlightContest",
        "min_zoom": 0,
        "max_zoom": 18,
        "default_zoom": 12,
        "is_overlay": False,
    },
    "mto": {
        "label": "MapTiler Outdoor",
        "type": "raster_xyz",
        "tile_url": "https://api.maptiler.com/maps/outdoor/{z}/{x}/{y}.png?key=YxHsFU6aEqsEULL34uJT",
        "attribution": "maptiler.com",
        "min_zoom": 0,
        "max_zoom": 18,
        "default_zoom": 12,
        "is_overlay": False,
    },
    "cyclosm": {
        "label": "CycleOSM",
        "type": "raster_xyz",
        "tile_url": "https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png",
        "attribution": "openstreetmap.org CycleOSM",
        "min_zoom": 0,
        "max_zoom": 20,
        "default_zoom": 12,
        "is_overlay": False,
    },
    "openaip": {
        "label": "OpenAIP",
        "type": "raster_xyz",
        "tile_url": "https://api.tiles.openaip.net/api/data/openaip/{z}/{x}/{y}.png?apiKey=3d5d3f82528731731362a23f445951d8",
        "attribution": "OpenAIP Data",
        "min_zoom": 4,
        "max_zoom": 14,
        "default_zoom": 10,
        "is_overlay": True,
    },
}

SWEDEN_250 = "Sweden250k"
SWEDEN_100 = "Sweden100k"
SWEDEN_250_OPSTIC = "Sweden250K_Opstic"
NORWAY_250 = "Norway250k"
NORWAY_M517 = "NorwayM517"
FINLAND_200 = "Finland200k"


def folder_map_name(folder: str) -> str:
    actual_map = folder.split("/")[-1]
    elements = actual_map.split("_")
    return " ".join([item.capitalize() for item in elements])


def get_map_filename(url: str) -> str:
    return url.split("/")[-1]


def is_user_uploaded_service_url(url: str) -> bool:
    return "/services/user-uploaded/" in url or "/services/user-uploaded-map-" in url


def get_builtin_map_source_definitions() -> list[dict]:
    definitions = []
    for key, source in BUILTIN_NON_MBTILES_SOURCES.items():
        definitions.append({"key": key, "provider": key, **source})

    for system_map_data in get_available_maps():
        if is_user_uploaded_service_url(system_map_data["url"]):
            continue
        key = get_map_filename(system_map_data["url"])
        details = get_map_details(key)
        definitions.append(
            {
                "key": key,
                "label": system_map_data["name"],
                "provider": "mbtiles",
                "type": "mbtiles",
                "tile_url": (details.get("tiles") or [system_map_data["url"]])[0],
                "attribution": system_map_data.get("attribution", ""),
                "min_zoom": details.get("minzoom", 0),
                "max_zoom": details.get("maxzoom", 18),
                "default_zoom": DEFAULT_MAP_ZOOM_LEVELS.get(key),
                "is_overlay": True,
                "bounds": details.get("bounds"),
            }
        )
    return definitions


def get_map_source_definition(map_source_key: str) -> dict:
    for definition in get_builtin_map_source_definitions():
        if definition["key"] == map_source_key:
            return definition
    raise KeyError(map_source_key)


def resolve_map_source_definition(map_source_key: str, user_uploaded_map=None) -> dict:
    if user_uploaded_map is not None:
        return {
            "key": str(user_uploaded_map.pk),
            "label": user_uploaded_map.name,
            "provider": "user_uploaded_mbtiles",
            "type": "mbtiles",
            "tile_url": f"{MBTILES_PUBLIC_URL.rstrip('/')}/services/user-uploaded/{user_uploaded_map.published_service_key}/tiles/{{z}}/{{x}}/{{y}}.png" if user_uploaded_map.published_service_key else "",
            "attribution": user_uploaded_map.attribution,
            "min_zoom": user_uploaded_map.minimum_zoom_level,
            "max_zoom": user_uploaded_map.maximum_zoom_level,
            "default_zoom": user_uploaded_map.default_zoom_level,
            "is_overlay": False,
            "bounds": user_uploaded_map.bounds,
        }
    return get_map_source_definition(map_source_key)


def map_source_definition_to_payload(definition: dict, origin: str = "builtin") -> dict:
    return {
        "key": definition["key"],
        "label": definition["label"],
        "origin": origin,
        "type": definition["type"],
        "tile_url": definition["tile_url"],
        "attribution": definition["attribution"],
        "min_zoom": definition["min_zoom"],
        "max_zoom": definition["max_zoom"],
        "default_zoom": definition["default_zoom"],
        "is_overlay": definition["is_overlay"],
        "bounds": definition.get("bounds"),
    }


def get_map_choices() -> list[tuple[str, str]]:
    return [(definition["key"], definition["label"]) for definition in get_builtin_map_source_definitions()]


def country_code_to_map_source(country_code: str) -> str:
    if not country_code:
        return "cyclosm"
    code = str(country_code).lower()
    return {"no": NORWAY_250, "fi": FINLAND_200, "se": SWEDEN_250_OPSTIC}.get(code, "cyclosm")


DEFAULT_MAP_ZOOM_LEVELS = {
    NORWAY_250: 12,
    FINLAND_200: 12,
    SWEDEN_100: 12,
    SWEDEN_250: 12,
    NORWAY_M517: 12,
    SWEDEN_250_OPSTIC: 12,
}
MAP_ATTRIBUTIONS = {
    NORWAY_250: "Contains data from kartverket.no, 07/2023",
    NORWAY_M517: "Avinor March 2024",
    FINLAND_200: "Contains data from the National Land Survey of Finland Topographic Database 07/2023",
    SWEDEN_100: "Contains data from lentmateriet.se, 07/2023",
    SWEDEN_250: "Contains data from lentmateriet.se, 02/2024",
    SWEDEN_250_OPSTIC: "Contains data from lentmateriet.se, 04/2025",
}


def get_map_zoom_levels() -> dict[str, tuple[int, int, int]]:
    from display.models import UserUploadedMap

    zoom_levels = {
        definition["key"]: (definition["min_zoom"], definition["max_zoom"], definition["default_zoom"])
        for definition in get_builtin_map_source_definitions()
    }
    for user_uploaded_map in UserUploadedMap.objects.all():
        zoom_levels[user_uploaded_map.pk] = (
            user_uploaded_map.minimum_zoom_level,
            user_uploaded_map.maximum_zoom_level,
            user_uploaded_map.default_zoom_level,
        )
    return zoom_levels


def qr_code_image(url: str, image_path: str):
    # taking image which user wants
    # in the QR code center
    logo = Image.open(image_path)

    # taking base width
    basewidth = 150

    # adjust image size
    wpercent = basewidth / float(logo.size[0])
    hsize = int((float(logo.size[1]) * float(wpercent)))
    logo = logo.resize((basewidth, hsize), Image.LANCZOS)
    QRcode = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    # addingg URL or text to QRcode
    QRcode.add_data(url)

    # generating QR code
    QRcode.make()

    # taking color name from user
    QRcolor = "black"

    # adding color to QR code
    QRimg = QRcode.make_image(fill_color=QRcolor, back_color="white").convert("RGB")

    # set size of QR code
    pos = ((QRimg.size[0] - logo.size[0]) // 2, (QRimg.size[1] - logo.size[1]) // 2)
    QRimg.paste(logo, pos)

    # save the QR code generated
    return QRimg
