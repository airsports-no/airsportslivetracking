from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
import qrcode

from guardian.shortcuts import get_objects_for_user

from live_tracking_map.settings import MBTILES_PUBLIC_URL
from display.flight_order_and_maps.mbtiles_facade import get_available_maps, get_map_details


def to_public_mbtiles_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path if parsed.scheme or parsed.netloc else url
    return f"{MBTILES_PUBLIC_URL.rstrip('/')}{path}"

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
    parsed = urlparse(url)
    path = parsed.path or url
    path_obj = Path(path.rstrip("/"))
    if len(path_obj.parts) >= 3 and path_obj.parts[-2] == "services":
        return path_obj.name
    if len(path_obj.parts) >= 4 and path_obj.parts[-3] == "services":
        return "/".join(path_obj.parts[-2:])
    return path_obj.name


def service_key_from_uploaded_relative_path(relative_path: str) -> str:
    return Path(relative_path).stem


def uploaded_map_token(user_uploaded_map) -> str:
    return f"user_uploaded:{user_uploaded_map.pk}"


def parse_uploaded_map_token(value: str) -> int | None:
    if not value or not str(value).startswith("user_uploaded:"):
        return None
    try:
        return int(str(value).split(":", 1)[1])
    except (TypeError, ValueError):
        return None


def route_extent_to_bounds(route) -> tuple[float, float, float, float] | None:
    try:
        minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude = route.get_extent()
    except (TypeError, ValueError):
        return None
    return minimum_longitude, minimum_latitude, maximum_longitude, maximum_latitude


def bounds_intersect(a: tuple[float, float, float, float] | list[float], b: tuple[float, float, float, float] | list[float]) -> bool:
    west_a, south_a, east_a, north_a = a
    west_b, south_b, east_b, north_b = b
    return not (east_a < west_b or east_b < west_a or north_a < south_b or north_b < south_a)


def source_definition_from_user_uploaded_map(user_uploaded_map) -> dict:
    relative_path = getattr(user_uploaded_map, "published_relative_path", "") or getattr(
        user_uploaded_map, "default_published_relative_path", ""
    )
    service_key = service_key_from_uploaded_relative_path(relative_path) if relative_path else getattr(
        user_uploaded_map, "published_service_key", ""
    )
    return {
        "key": uploaded_map_token(user_uploaded_map),
        "label": user_uploaded_map.name,
        "provider": "user_uploaded_mbtiles",
        "type": "mbtiles",
        "tile_url": f"{MBTILES_PUBLIC_URL.rstrip('/')}/services/{service_key}/tiles/{{z}}/{{x}}/{{y}}.png" if service_key else "",
        "attribution": user_uploaded_map.attribution,
        "min_zoom": user_uploaded_map.minimum_zoom_level,
        "max_zoom": user_uploaded_map.maximum_zoom_level,
        "default_zoom": user_uploaded_map.default_zoom_level,
        "is_overlay": True,
        "allow_multiple": False,
        "is_always_on_top": False,
        "bounds": user_uploaded_map.bounds,
    }


def get_available_map_source_definitions_for_navigation_task(task, user, uploaded_maps=None) -> list[dict]:
    from display.models.user_uploaded_map import UserUploadedMap

    route_bounds = route_extent_to_bounds(task.route)
    definitions = []
    for definition in get_builtin_map_source_definitions():
        if definition["key"] == "openaip":
            continue
        if definition["provider"] != "mbtiles":
            definitions.append(definition)
            continue
        if route_bounds and definition.get("bounds") and bounds_intersect(definition["bounds"], route_bounds):
            definitions.append(definition)

    if uploaded_maps is None:
        uploaded_maps = get_objects_for_user(
            user,
            "display.view_useruploadedmap",
            klass=UserUploadedMap,
            accept_global_perms=False,
        ).filter(processing_status=UserUploadedMap.PROCESSING_READY).exclude(published_service_key="")
    else:
        uploaded_maps = uploaded_maps.filter(processing_status=UserUploadedMap.PROCESSING_READY).exclude(published_service_key="")
    for uploaded_map in uploaded_maps:
        if route_bounds and uploaded_map.bounds and bounds_intersect(uploaded_map.bounds, route_bounds):
            definitions.append(source_definition_from_user_uploaded_map(uploaded_map))
    return definitions


def get_available_map_source_choices_for_navigation_task(task, user) -> list[tuple[str, str]]:
    return [(definition["key"], definition["label"]) for definition in get_available_map_source_definitions_for_navigation_task(task, user)]


def get_map_zoom_levels_for_definitions(definitions: list[dict]) -> dict[str, tuple[int, int, int]]:
    return {
        definition["key"]: (definition["min_zoom"], definition["max_zoom"], definition["default_zoom"])
        for definition in definitions
    }


def resolve_uploaded_map_from_token(map_source_key: str):
    uploaded_pk = parse_uploaded_map_token(map_source_key)
    if uploaded_pk is None:
        return None
    from display.models.user_uploaded_map import UserUploadedMap

    return UserUploadedMap.objects.filter(pk=uploaded_pk).first()


def is_user_uploaded_service_url(url: str) -> bool:
    return "/services/user-uploaded/" in url or "/services/user-uploaded-map-" in url or "/services/user_uploaded_maps/" in url


def get_builtin_map_source_definitions() -> list[dict]:
    definitions = []
    for key, source in BUILTIN_NON_MBTILES_SOURCES.items():
        definitions.append({"key": key, "provider": key, **source, "allow_multiple": key == "openaip", "is_always_on_top": key == "openaip"})

    from display.models.user_uploaded_map import UserUploadedMap

    uploaded_service_keys = {
        service_key_from_uploaded_relative_path(uploaded_map.published_relative_path)
        for uploaded_map in UserUploadedMap.objects.exclude(published_relative_path="")
        if uploaded_map.published_relative_path
    }

    for system_map_data in get_available_maps():
        if is_user_uploaded_service_url(system_map_data["url"]):
            continue
        parsed = urlparse(system_map_data["url"])
        path = parsed.path or system_map_data["url"]
        key = get_map_filename(system_map_data["url"])
        if key in uploaded_service_keys:
            continue
        details = get_map_details(key)
        definitions.append(
            {
                "key": key,
                "label": system_map_data["name"],
                "provider": "mbtiles",
                "type": "mbtiles",
                "tile_url": to_public_mbtiles_url((details.get("tiles") or [system_map_data["url"]])[0]),
                "attribution": system_map_data.get("attribution", ""),
                "min_zoom": details.get("minzoom", 0),
                "max_zoom": details.get("maxzoom", 18),
                "default_zoom": DEFAULT_MAP_ZOOM_LEVELS.get(key),
                "is_overlay": True,
                "allow_multiple": False,
                "is_always_on_top": False,
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
        return source_definition_from_user_uploaded_map(user_uploaded_map)
    if uploaded_map := resolve_uploaded_map_from_token(map_source_key):
        return source_definition_from_user_uploaded_map(uploaded_map)
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
        "allow_multiple": definition.get("allow_multiple", False),
        "is_always_on_top": definition.get("is_always_on_top", False),
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
        zoom_levels[uploaded_map_token(user_uploaded_map)] = (
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
