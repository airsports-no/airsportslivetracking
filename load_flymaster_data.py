import json
import subprocess


with open("parsed_flymaster_posts_task1and2.json", "r") as o:
    data = json.load(o)
    for index, item in enumerate(data):
        print(index)
        subprocess.call(["curl", "-F", f"data={item}", "https://app.airsports.no/display/flymaster/"])
