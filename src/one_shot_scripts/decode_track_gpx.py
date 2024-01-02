import base64

with open("../data/fredrik2019gpx.base64", "r") as f:
    track_string = base64.b64decode(f.read().encode('utf-8')).decode('utf-8')
with open("../data/fredrik2019.gpx", "w") as o:
    o.write(track_string)
