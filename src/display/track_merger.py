from typing import List, Dict


def merge_tracks(tracks: List[List["Position"]]) -> List["Position"]:
    maximum = max(len(i) for i in tracks)
    for t in tracks:
        if len(t) == maximum:
            return t
    return []
