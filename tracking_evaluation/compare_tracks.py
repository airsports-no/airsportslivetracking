import gpxpy.gpx
import numpy as np

base = "espen_test"

sources = ["app", "traccar", "airsports"]

tracks = {}

for source in sources:
    with open(f"{base}_{source}.gpx", "r") as file:
        gpx = gpxpy.parse(file)
        for position in gpx.tracks[0].segments[0].points:
            try:
                tracks[position.time].append((source, position))
            except KeyError:
                tracks[position.time] = [(source, position)]

times = sorted(tracks.keys())
fractional_digits=5
previous_app= None
for stamp in times:
    present_sources = set(item[0] for item in tracks[stamp])
    position_differences = {}
    for source, position in tracks[stamp]:
        if source=="app":
            previous_app=position
        key = (np.around(position.latitude, fractional_digits), np.around(position.longitude, fractional_digits))
        try:
            position_differences[key].append(source)
        except KeyError:
            position_differences[key] = [source]
    # if "app" not in present_sources and previous_app:
    #     present_sources.add("app_delayed")
    #     key = (np.around(previous_app.latitude, fractional_digits), np.around(previous_app.longitude, fractional_digits))
    #     try:
    #         position_differences[key].append("app")
    #     except KeyError:
    #         position_differences[key] = ["app"]

    print(
        f"At time {stamp}: {sorted(present_sources)} {f'Differences: {position_differences}' if len(position_differences) > 1 else ''}"
    )
    # if len(tracks[stamp]) != len(sources):
    #     present_sources = set(item[0] for item in tracks[stamp])
    #     print(f"At time {stamp}: Missing {set(sources) - present_sources}")

# <trkpt lat="59.944911" lon="10.604776">
# <trkpt lat="59.9449180319371" lon="10.604778037621882">
# trkpt lat="59.944918" lon="10.604778">