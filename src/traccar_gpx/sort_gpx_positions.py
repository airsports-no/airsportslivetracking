import gpxpy

with open("track.gpx", "r") as f:
    gpx = gpxpy.parse(f)
    track = gpx.tracks[0]
    segment = track.segments[0]
    points = sorted(segment.points, key=lambda k:k.time)
    segment.points = points
with open("sortedtrack.gpx", "w") as f:
    f.write(gpx.to_xml())
