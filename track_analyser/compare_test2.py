from datetime import timezone

from track_analyser.compare_tracks import (
    compare_maximum_confidences,
    compare_everything,
    plot_difference_compared_to_single,
)
from track_analyser.gps_track import GPSTrack
from datetime_modulo import datetime

folder = "tracks/test2"

loggers = [
    GPSTrack.load_gpx("Logger 1", f"{folder}/05.gpx"),
    GPSTrack.load_gpx("Logger 2", f"{folder}/07.gpx"),
    GPSTrack.load_gpx("Logger 3", f"{folder}/03.gpx"),
    GPSTrack.load_gpx("Logger 4", f"{folder}/09.gpx"),
]

# androids = [GPSTrack.load_gpx("App1 (1 sek)", f"{folder}/kolaf.gpx")]
androids = []
iphones = [
    GPSTrack.load_gpx("espen", f"{folder}/espen.gpx"),
    GPSTrack.load_gpx("chuck", f"{folder}/chuck.gpx"),
    GPSTrack.load_gpx("Viste", f"{folder}/viste.gpx"),
    # GPSTrack.load_gpx("App2 (5 sek, extgps)", f"{folder}/chuck.gpx"),
]

start_time = datetime(2022, 4, 2, 11, 50, tzinfo=timezone.utc)
finish_time = datetime(2022, 4, 2, 12, 45, tzinfo=timezone.utc)
for tracker in loggers + androids + iphones:
    tracker.clip_track(start_time, finish_time)

plot_difference_compared_to_single(loggers[0], loggers + androids + iphones, folder)

compare_everything(
    loggers + androids + iphones, f"loggers_and_androids_and_iphones", folder
)

compare_maximum_confidences(loggers, loggers + androids + iphones, 0.99, folder)
compare_maximum_confidences(loggers, loggers + androids + iphones, 0.95, folder)
