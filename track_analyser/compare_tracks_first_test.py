from typing import List

from cartopy.io.img_tiles import OSM

from track_analyser.compare_tracks import compare_maximum_confidences
from track_analyser.gps_track import GPSTrack
import numpy as np
import matplotlib.pyplot as plt

from track_analyser.track_comparator import get_track_differences

loggers = [
    GPSTrack.load_gpx("Logger 1", "tracks/06.gpx"),
    GPSTrack.load_gpx("Logger 2", "tracks/07.gpx"),  # bad?
    GPSTrack.load_gpx("Logger 3", "tracks/Gulbrand.gpx"),
    GPSTrack.load_gpx("Logger 4", "tracks/royaltek.gpx"),
]

androids = [GPSTrack.load_gpx("App1 (1 sek)", "tracks/kolaf fra kjeller.gpx")]

iphones = [
    GPSTrack.load_gpx("App1 (5 sek)", "tracks/espen fra kjeller.gpx"),
    GPSTrack.load_gpx("App2 (5 sek)", "tracks/chuck fra kjeller.gpx"),
]

scores = [
    ["Logger 1", 846],
    ["Logger 2", 846],
    ["Logger 3", 846],
    ["Logger 4", 846],
    ["App1 (1 sek)", 849],
    ["App1 (5 sek)", 843],
    ["App2 (5 sek)", 843],
]



# compare_everything(loggers + iphones, "loggers_and_iphones")
# compare_everything(loggers + androids, "loggers_and_androids")
# plot_scores()
# compare_everything(loggers + androids + iphones, "loggers_and_androids_and_iphones")
# compare_everything(loggers, "all_loggers")
# plot_tracks(loggers, "tracks_all_loggers.png")
# plot_tracks(loggers+androids, "tracks_all_loggers_androids.png")

# plot_confidence_compared_with_single_logger(
#     loggers[0], loggers + androids + iphones, 0.99
# )
# plot_confidence_compared_with_single_logger(
#     loggers[0], loggers + androids + iphones, 0.95
# )

compare_maximum_confidences(loggers, loggers + androids + iphones, 0.99)
compare_maximum_confidences(loggers, loggers + androids + iphones, 0.95)
