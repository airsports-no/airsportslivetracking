import requests

session = requests.session()
data = requests.get("http://localhost:8000/api/v1/tracks/312/")
print(len(data.json()["track"]))
