import datetime
import math
import threading
import time
from typing import Dict
from urllib.parse import urlencode

from SimConnect import *
import requests
from requests import HTTPError

from my_firebase import initialize_app

config = {
    "apiKey": "AIzaSyCcOlh07D2-7p0W2coNK_sZ2g8-JxxbPSE",
    "authDomain": "airsports-613ce.firebaseapp.com",
    "databaseURL": "https://airsports-613ce.firebaseio.com",
    "storageBucket": "airsports-613ce.appspot.com"
}

firebase = initialize_app(config)
authenticator = firebase.auth()

# TRACKING_ID = "0x2nXGmVbQ7s5hJ3Y49xATolpSOf"  # Meg sim
# TRACKING_ID = "52KQSqtVybuKlpXgV5KpDwX9ia0t" # Me app
# TRACKING_ID = "Ia4oiwa1lxFfjJR9cKorkOpn5o9V"  # Jonas app
tracking_event = threading.Event()

class MissingEmailVerificationError(Exception):
    pass

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
        if tracking_event.is_set():
            return
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


def save_profile(profile: Dict, user: Dict):
    print("Saving profile")
    profile["validated"] = True
    del profile["picture"]
    response = requests.put("https://airsports.no/api/v1/userprofile/update_profile/",
                            headers={'Authorization': "JWT {}".format(user["idToken"])},
                            data=profile)
    print(response.status_code)
    print(response.text)
    if response.status_code == 200:
        return True
    return False


def fetch_profile_image_data(image_url) -> bytearray:
    return requests.get(image_url).content


if __name__ == "__main__":
    import PySimpleGUI as sg

    authentication = [
        [sg.Text("Login or create new account")],
        [sg.Text("Email"), sg.InputText(size=(50, 1), key="EMAIL")],
        [sg.Text("Password"), sg.InputText(size=(40, 1), key="PASSWORD", password_char="*")],
        [sg.Button("Login"), sg.Button("Signup")],
        [sg.Button("Start tracking", key="START_TRACKING", visible=False)],
        [sg.Button("Stop tracking", key="STOP_TRACKING", visible=False)],
        [sg.HSeparator()],
        [sg.Button("Quit")],
    ]
    profile = [
        [sg.Text(size=(50, 1), key="FIRST_NAME"), sg.Button("Update", key="UPDATE_FIRST_NAME", visible=False)],
        [sg.Text(size=(50, 1), key="LAST_NAME"), sg.Button("Update", key="UPDATE_LAST_NAME", visible=False)],
        [sg.Button("Save profile", key="SAVE_PROFILE", visible=False)],
        [sg.Image(key="PROFILE_IMAGE", size=(100, 100))]

    ]

    layout = [
        [
            sg.Column(authentication),
            sg.VSeparator(),
            sg.Column(profile)
        ]
    ]
    window = sg.Window(title="Airsports Live Tracking MSFS2020", layout=layout, margins=(20, 20))
    profile = None
    user = None
    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "Quit" or event == sg.WIN_CLOSED:
            break
        if event == "Login":
            try:
                user = authenticator.sign_in_with_email_and_password(values["EMAIL"], values["PASSWORD"])
                print(user)
                user_account = authenticator.get_account_info(user["idToken"])
                print(user_account)
                user_account = user_account["users"][0]
                if not user_account["emailVerified"]:
                    raise MissingEmailVerificationError("User email is not verified")
                profile = fetch_profile(user)
                window["Login"].update(disabled=True)
                window["Signup"].update(disabled=True)
                window["START_TRACKING"].update(visible=True)
                window["SAVE_PROFILE"].update(visible=True)
                window["UPDATE_FIRST_NAME"].update(visible=True)
                window["UPDATE_LAST_NAME"].update(visible=True)
                window["FIRST_NAME"].update(profile["first_name"])
                window["LAST_NAME"].update(profile["last_name"])
                window["PROFILE_IMAGE"].update(data=fetch_profile_image_data(profile["picture"]))
            except HTTPError as e:
                print(e)
                sg.popup(str(e))
            except MissingEmailVerificationError:
                user = None
                sg.popup("Email address is not verified, please check your inbox")
        if event == "Signup":
            try:
                new_user = authenticator.create_user_with_email_and_password(values["EMAIL"], values["PASSWORD"])
                print(new_user)
                authenticator.send_email_verification(new_user['idToken'])
                sg.popup("Verification", "Signup complete, please check for verification email before signing in.")
            except HTTPError as e:
                print(e)
                sg.popup(str(e))
        if event == "UPDATE_FIRST_NAME":
            profile["first_name"] = sg.popup_get_text("First name", "Please update your first name",
                                                      default_text=profile["first_name"])
            window["FIRST_NAME"].update(profile["first_name"])
        if event == "UPDATE_LAST_NAME":
            profile["last_name"] = sg.popup_get_text("Last name", "Please update your last name",
                                                     default_text=profile["last_name"])
            window["LAST_NAME"].update(profile["last_name"])
        if event == "SAVE_PROFILE":
            if user is not None:
                if save_profile(profile, user):
                    sg.popup("Success", "Profile saved successfully")
                else:
                    sg.popup("Failure", "Saving user profile failed")
            else:
                sg.popup("Error", "You are not logged in")
        if event == "START_TRACKING":
            tracking_event.clear()
            window["START_TRACKING"].update(visible=False)
            window["STOP_TRACKING"].update(visible=True)
            run(profile["simulator_tracking_id"])

        if event == "STOP_TRACKING":
            window["START_TRACKING"].update(visible=True)
            window["STOP_TRACKING"].update(visible=False)
            tracking_event.set()

    window.close()
