from datetime import timezone, timedelta

from track_analyser.compare_tracks import (
    compare_maximum_confidences,
    compare_everything,
    plot_difference_compared_to_single, compare_mean_with_confidences,
)
from track_analyser.gps_track import GPSTrack
from datetime_modulo import datetime

folder = "tracks/thomlevold"

loggers = [
    GPSTrack.load_gpx("Logger 1", f"{folder}/05.gpx"),
    GPSTrack.load_gpx("Logger 2", f"{folder}/07.gpx"),
    GPSTrack.load_gpx("Logger 3", f"{folder}/03.gpx"),
    GPSTrack.load_gpx("Logger 4", f"{folder}/09.gpx"),
]

androids = [
    GPSTrack.load_gpx("Android1 (1 sek)", f"{folder}/frankolaf.gpx"),
    GPSTrack.load_gpx("Android2 (1 sek)", f"{folder}/gulbrand.gpx")
]

iphones = [
    GPSTrack.load_gpx("Iphone1 (1 sek)", f"{folder}/espen.gpx"),
    GPSTrack.load_gpx("Iphone2 (1 sek)", f"{folder}/andersmagnus.gpx"),
    GPSTrack.load_gpx("Iphone3 (1 sek)", f"{folder}/hedvig.gpx"),
    # GPSTrack.load_gpx("Iphone4 (5 sek)", f"{folder}/rune.gpx"),
    GPSTrack.load_gpx("Iphone5 (1 sek)", f"{folder}/mikael.gpx"),
]

start_time = datetime(2022, 6, 4, 13, 50, tzinfo=timezone.utc)
finish_time = datetime(2022, 6, 4, 15, 0, tzinfo=timezone.utc)
for tracker in loggers + androids + iphones:
    tracker.clip_track(start_time, finish_time)

compare_mean_with_confidences(loggers, loggers + androids + iphones, 0.95, folder)
# compare_mean_with_confidences(loggers, loggers + androids + iphones, 0.2, folder)
# compare_mean_with_confidences(androids + iphones, androids + iphones, 0.95, folder)
# compare_mean_with_confidences(androids + iphones, androids + iphones, 0.2, folder)
#
#
# plot_difference_compared_to_single(loggers[0], loggers + androids + iphones, folder)
# plot_difference_compared_to_single(loggers[1], loggers + androids + iphones, folder)
# plot_difference_compared_to_single(loggers[2], loggers + androids + iphones, folder)
# plot_difference_compared_to_single(loggers[3], loggers + androids + iphones, folder)
#
# compare_everything(
#     loggers + androids + iphones, f"loggers_and_androids_and_iphones", folder
# )
#
# compare_maximum_confidences(loggers, loggers + androids + iphones, 0.99, folder)
# compare_maximum_confidences(loggers, loggers + androids + iphones, 0.95, folder)
# compare_maximum_confidences(loggers, loggers + androids + iphones, 0.2, folder)
# compare_mean_with_confidences(loggers, loggers + androids + iphones, 0.95, folder)