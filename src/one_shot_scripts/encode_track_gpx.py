import base64

with open("../../data/tracks/Frank-Olaf.gpx", "r") as f:
    track_string = base64.b64encode(f.read().encode('utf-8')).decode('utf-8')
data = {
    "track_file":track_string
}
print(data)