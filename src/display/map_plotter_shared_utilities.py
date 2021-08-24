import glob

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


MAP_FOLDERS = glob.glob("/maptiles/*")
MAP_CHOICES = [(item, folder_map_name(item)) for item in MAP_FOLDERS] + [
    ("osm", "OSM"),
    ("fc", "Flight Contest"),
    ("mto", "MapTiler Outdoor"),
    ("cyclosm", "CycleOSM")
]