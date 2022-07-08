from datetime import timezone, timedelta

from track_analyser.compare_tracks import (
    compare_maximum_confidences,
    compare_everything,
    plot_difference_compared_to_single, compare_mean_with_confidences,
)
from track_analyser.gps_track import GPSTrack
from datetime_modulo import datetime

folder = "tracks/trening 14.06.22"

loggers = [
    GPSTrack.load_gpx("Logger 1", f"{folder}/05.gpx"),
    GPSTrack.load_gpx("Logger 2", f"{folder}/07.gpx"),
    GPSTrack.load_gpx("Logger 3", f"{folder}/03.gpx"),
    GPSTrack.load_gpx("Logger 4", f"{folder}/09.gpx"),
]

androids = [
    GPSTrack.load_gpx("Android1 (1 sek)", f"{folder}/frankolaf.gpx"),
]

iphones = [
    GPSTrack.load_gpx("Iphone1 (1 sek)", f"{folder}/espen.gpx"),
]

start_time = datetime(2022, 6, 14, 15, 35, tzinfo=timezone.utc)
finish_time = datetime(2022, 6, 14, 17, 0, tzinfo=timezone.utc)
for tracker in loggers + androids + iphones:
    tracker.clip_track(start_time, finish_time)

compare_mean_with_confidences(loggers, loggers + androids + iphones, 0.95, folder)
# compare_mean_with_confidences(androids + iphones, androids + iphones, 0.95, folder)
#
#
plot_difference_compared_to_single(loggers[0], loggers + androids + iphones, folder)
plot_difference_compared_to_single(loggers[1], loggers + androids + iphones, folder)
plot_difference_compared_to_single(loggers[2], loggers + androids + iphones, folder)
plot_difference_compared_to_single(loggers[3], loggers + androids + iphones, folder)

compare_everything(
    loggers + androids + iphones, f"loggers_and_androids_and_iphones", folder
)

compare_maximum_confidences(loggers, loggers + androids + iphones, 0.99, folder)
compare_maximum_confidences(loggers, loggers + androids + iphones, 0.95, folder)
compare_mean_with_confidences(loggers, loggers + androids + iphones, 0.95, folder)