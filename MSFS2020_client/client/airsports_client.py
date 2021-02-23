import datetime
import math
import threading
import time
from typing import Dict
from urllib.parse import urlencode

from SimConnect import *
import requests
import pyrebase
from requests import HTTPError

config = {
    "apiKey": "AIzaSyCcOlh07D2-7p0W2coNK_sZ2g8-JxxbPSE",
    "authDomain": "airsports-613ce.firebaseapp.com",
    "databaseURL": "https://airsports-613ce.firebaseio.com",
    "storageBucket": "airsports-613ce.appspot.com"
}

firebase = pyrebase.initialize_app(config)
authenticator = firebase.auth()


# TRACKING_ID = "0x2nXGmVbQ7s5hJ3Y49xATolpSOf"  # Meg sim
# TRACKING_ID = "52KQSqtVybuKlpXgV5KpDwX9ia0t" # Me app
# TRACKING_ID = "Ia4oiwa1lxFfjJR9cKorkOpn5o9V"  # Jonas app


def load_tracking_id():
    with open("client.cfg", "r") as i:
        return i.readline().strip()


def send(id, time, lat, lon, speed, altitude, course):
    params = (
        ('id', id), ('timestamp', int(time)), ('lat', lat), ('lon', lon), ('speed', speed), ('altitude', altitude),
        ('heading', course * 180 / math.pi))
    print(f"Posting position: {params}")
    try:
        response = requests.post("https://traccar.airsports.no/?" + urlencode(params))
        print(response.status_code)
        print(response.text)
    except:
        print("Sending failed")


def run(tracking_id):
    print(f"Running with ID: '{tracking_id}'")
    failed = True
    while failed:
        failed = False
        try:
            # Create SimConnect link
            sm = SimConnect()
        except ConnectionError:
            print("Failed connecting")
            return
            # failed = True
    print("Got link")
    # Note the default _time is 2000 to be refreshed every 2 seconds
    aq = AircraftRequests(sm, _time=2000)
    print("Created aircraft requests")

    def transmit_position():
        altitude = aq.get("PLANE_ALTITUDE")
        latitude = aq.get("PLANE_LATITUDE")
        longitude = aq.get("PLANE_LONGITUDE")
        velocity = aq.get("GROUND_VELOCITY")
        course = aq.get("PLANE_HEADING_DEGREES_TRUE")
        now = datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
        print(now)
        if longitude != 0 and latitude != 0 and longitude is not None and latitude is not None:
            send(tracking_id, time.mktime(now.timetuple()), latitude, longitude, velocity, altitude, course)
        threading.Timer(2, transmit_position).start()

    transmit_position()


def fetch_profile(user: Dict):
    response = requests.get("https://airsports.no/api/v1/userprofile/retrieve_profile/",
                            headers={'Authorization': "JWT {}".format(user["idToken"])}
                            )
    print(response.status_code)
    print(response.text)
    if response.status_code == 200:
        return response.json()


if __name__ == "__main__":
    import PySimpleGUI as sg

    layout = [[sg.Text("Login or create new account")],
              [sg.Text("Email"), sg.InputText(size=(50, 1), key="EMAIL"), sg.Text("Password"),
               sg.InputText(size=(40, 1), key="PASSWORD")], [sg.Button("Login"), sg.Button("Signup")],
              [sg.Button("Quit")]]
    window = sg.Window(title="Airsports Live Tracking MSFS2020", layout=layout, margins=(20, 20))
    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "Quit" or event == sg.WIN_CLOSED:
            break
        if event == "Login":
            try:
                result = authenticator.sign_in_with_email_and_password(values["EMAIL"], values["PASSWORD"])
                print(result)
                profile = fetch_profile(result)
                sg.popup(f"Hello {profile['first_name']} {profile['last_name']}")
                tracking_id = profile["simulator_tracking_id"]
                window["Login"].update(disabled=True)
                window["Signup"].update(disabled=True)
                run(tracking_id)
            except HTTPError as e:
                print(e)
                sg.popup(str(e))
        if event == "Signup":
            try:
                user = authenticator.create_user_with_email_and_password(values["EMAIL"], values["PASSWORD"])
                print(user)
                authenticator.send_email_verification(user['idToken'])
            except HTTPError as e:
                print(e)
                sg.popup(str(e))
    window.close()
