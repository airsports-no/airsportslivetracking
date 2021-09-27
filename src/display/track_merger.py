from typing import List, Dict


def merge_tracks(tracks: List[List["Position"]]) -> List["Position"]:
    try:
        return tracks[0]
    except IndexError:
        return []
