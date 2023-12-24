from PIL import Image
import qrcode

from display.flight_order_and_maps.mbtiles_facade import get_available_maps, get_map_details


def folder_map_name(folder: str) -> str:
    actual_map = folder.split("/")[-1]
    elements = actual_map.split("_")
    return " ".join([item.capitalize() for item in elements])


def get_map_choices() -> list[tuple[str, str]]:
    return [(item["url"].split("/")[-1], item["name"]) for item in get_available_maps()] + [
        ("osm", "OSM"),
        ("fc", "Flight Contest"),
        ("mto", "MapTiler Outdoor"),
        ("cyclosm", "CycleOSM"),
    ]


def country_code_to_map_source(country_code: str) -> str:
    return {"no": "Norway250k", "fi": "Finland200k", "se": "Sweden100k"}.get(country_code, "cyclosm")


DEFAULT_MAP_ZOOM_LEVELS = {"Norway250k": 12, "Finland200k": 12, "Sweden100k": 12}
MAP_ATTRIBUTIONS = {
    "Norway250k": "Contains data from kartverket.no, 07/2023",
    "Finland200k": "Contains data from the National Land Survey of Finland Topographic Database 07/2023",
    "Sweden100k": "Contains data from lentmateriet.se, 07/2023",
}


def get_map_zoom_levels() -> dict[str, tuple[int, int, int]]:
    from display.models import UserUploadedMap

    zoom_levels = {}
    for system_map_data in get_available_maps():
        system_map = system_map_data["name"]
        details = get_map_details(system_map)
        zoom_levels[system_map] = (details["minzoom"], details["maxzoom"], DEFAULT_MAP_ZOOM_LEVELS.get(system_map))
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
