from typing import List

from display.models.contestant_utility_models import ContestantReceivedPosition


def merge_tracks(tracks: List[List[ContestantReceivedPosition]]) -> List[ContestantReceivedPosition]:
    maximum = max(len(i) for i in tracks) if len(tracks) else -1
    for t in tracks:
        if len(t) == maximum:
            return t
    return []
