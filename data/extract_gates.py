import datetime
import time
from urllib.parse import urlencode

import requests
from fastkml import kml

id = '123456789012345'
server = '192.168.1.2:5055'

with open("NM-2020-1.kml", "r") as input_kml:
    document = input_kml.read()

kml_document = kml.KML()
kml_document.from_string(document)
document = list(kml_document.features())[0]
print(document)
folders = list(list(document.features())[0].features())
turnpoints = []
for folder in folders:
    print(folder.name)
    if folder.name == "Turnpoints":
        for item in folder.features():
            turnpoints.append((item.name, item.geometry.xy[0][0], item.geometry.xy[1][0], "tp", 2))
    elif folder.name == "Secrets":
        for item in folder.features():
            turnpoints.append((item.name, item.geometry.xy[0][0], item.geometry.xy[1][0], "secret", 2))
with open("NM.csv", "w") as o:
    o.write("\n")
    for item in turnpoints:
        o.write("{}\n".format(", ".join([str(a) for a in item])))
print(turnpoints)
