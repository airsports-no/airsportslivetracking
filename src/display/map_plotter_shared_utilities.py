import glob
import numpy as np
import cartopy.crs as ccrs
import utm

from PIL import Image
import qrcode

OSM_MAP = 0
N250_MAP = 1
M517_BERGEN_MAP = 2
GERMANY1 = 3
TILE_MAP = {
    N250_MAP: "Norway_N250",
    M517_BERGEN_MAP: "m517_bergen",
    GERMANY1: "germany_map",
}


def folder_map_name(folder: str) -> str:
    actual_map = folder.split("/")[-1]
    elements = actual_map.split("_")
    return " ".join([item.capitalize() for item in elements])


MAP_FOLDERS = ['/maptiles/Norway_N250']  # glob.glob("/maptiles/*")
MAP_CHOICES = [(item, folder_map_name(item)) for item in MAP_FOLDERS] + [
    ("osm", "OSM"),
    ("fc", "Flight Contest"),
    ("mto", "MapTiler Outdoor"),
    ("cyclosm", "CycleOSM")
]

def utm_from_lon(lon):
    """
    utm_from_lon - UTM zone for a longitude
    Not right for some polar regions (Norway, Svalbard, Antartica)
    :param float lon: longitude
    :return: UTM zone number
    :rtype: int
    """

    return np.floor((lon + 180) / 6) + 1


def utm_from_lat_lon(lat, lon) -> ccrs.CRS:
    """
    utm_from_lon - UTM zone for a longitude
    Not right for some polar regions (Norway, Svalbard, Antartica)
    :param float lon: longitude
    :return: UTM zone number
    :rtype: int
    """
    _, _, zone, letter = utm.from_latlon(lat, lon)
    print(zone)
    print(letter)
    return ccrs.UTM(zone, southern_hemisphere=lat < 0)


def qr_code_image(url: str, image_path: str):

    # taking image which user wants
    # in the QR code center
    logo = Image.open(image_path)

    # taking base width
    basewidth = 150

    # adjust image size
    wpercent = (basewidth / float(logo.size[0]))
    hsize = int((float(logo.size[1]) * float(wpercent)))
    logo = logo.resize((basewidth, hsize), Image.ANTIALIAS)
    QRcode = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H
    )
    # addingg URL or text to QRcode
    QRcode.add_data(url)

    # generating QR code
    QRcode.make()

    # taking color name from user
    QRcolor = 'black'

    # adding color to QR code
    QRimg = QRcode.make_image(
        fill_color=QRcolor, back_color="white").convert('RGB')

    # set size of QR code
    pos = ((QRimg.size[0] - logo.size[0]) // 2,
           (QRimg.size[1] - logo.size[1]) // 2)
    QRimg.paste(logo, pos)

    # save the QR code generated
    return QRimg
