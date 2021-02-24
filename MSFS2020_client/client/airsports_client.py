import datetime
import math
import threading
import time
from typing import Dict
from urllib.parse import urlencode
import PySimpleGUIWx as sg

from SimConnect import *
import requests
from requests import HTTPError

from client.my_firebase import initialize_app

currently_tracking = False

config = {
    "apiKey": "AIzaSyCcOlh07D2-7p0W2coNK_sZ2g8-JxxbPSE",
    "authDomain": "airsports.no",
    "databaseURL": "https://airsports-613ce.firebaseio.com",
    "storageBucket": "airsports-613ce.appspot.com"
}

firebase = initialize_app(config)
authenticator = firebase.auth()

tracking_event = threading.Event()


class MissingEmailVerificationError(Exception):
    pass


class MissingProfileError(Exception):
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


def run(tracking_id, stamp_field):
    global currently_tracking
    currently_tracking = True
    stamp_field.update("Connecting...")
    # print(f"Running with ID: '{tracking_id}'")
    failed = True
    while failed:
        failed = False
        try:
            # Create SimConnect link
            sm = SimConnect()
        except ConnectionError:
            print("Failed connecting")
            currently_tracking = False
            stamp_field.update("Connecting... failed")
            return
            # failed = True
    # print("Got link")
    # Note the default _time is 2000 to be refreshed every 2 seconds
    aq = AircraftRequests(sm, _time=2000)
    # print("Created aircraft requests")

    def transmit_position():
        global currently_tracking
        if tracking_event.is_set():
            currently_tracking = False
            return
        altitude = aq.get("PLANE_ALTITUDE")
        latitude = aq.get("PLANE_LATITUDE")
        longitude = aq.get("PLANE_LONGITUDE")
        velocity = aq.get("GROUND_VELOCITY")
        course = aq.get("PLANE_HEADING_DEGREES_TRUE")
        now = datetime.datetime.now().replace(tzinfo=datetime.timezone.utc)
        print(now)
        stamp_field.update(str(now))
        if longitude != 0 and latitude != 0 and longitude is not None and latitude is not None:
            send(tracking_id, time.mktime(now.timetuple()), latitude, longitude, velocity, altitude, course)
        threading.Timer(2, transmit_position).start()

    transmit_position()


class User:
    def __init__(self):
        self.user = None
        self.user_account = None
        self.user_token = None
        self.profile = None

    def sign_in(self, window, values):
        progress_bar = window["LOGIN_PROGRESS"]
        progress_bar.update_bar(1)
        try:
            self.user, self.user_account, self.user_token, self.profile = sign_in_user(values["EMAIL"],
                                                                                       values["PASSWORD"])
            window["Login"].update(disabled=True)
            window["Signup"].update(disabled=True)
            window["RESEND_VERIFICATION"].update(disabled=True)
            window["UPDATE_FIRST_NAME"].update(disabled=False)
            window["UPDATE_LAST_NAME"].update(disabled=False)
            window["FIRST_NAME"].update(self.profile["first_name"])
            window["LAST_NAME"].update(self.profile["last_name"])
            progress_bar.update_bar(3)
            if self.profile['validated']:
                window["START_TRACKING"].update(disabled=False)
            else:
                sg.popup("Please update profile to enable tracking")
            return True
            # window["PROFILE_IMAGE"].update(data=fetch_profile_image_data(profile["picture"]))
        except HTTPError as e:
            # print(e)
            sg.popup(str(e))
        except MissingEmailVerificationError:
            window["RESEND_VERIFICATION"].update(disabled=False)
            sg.popup("Email address is not verified, please check your inbox")
        except MissingProfileError as e:
            sg.popup(str(e))
        progress_bar.update_bar(0)
        return False

    def sign_up(self, window, values):
        try:
            new_user = authenticator.create_user_with_email_and_password(values["EMAIL"], values["PASSWORD"])
            # print(new_user)
            self.user_token = new_user["idToken"]
            try:
                authenticator.send_email_verification(new_user['idToken'])
            except HTTPError as e:
                sg.popup(str(e))
            sg.popup("Verification", "Signup complete, please check for verification email before signing in.")
            return True
        except HTTPError as e:
            # print(e)
            sg.popup(str(e))
        return False

    def save_profile(self, window):
        window["START_TRACKING"].update(disabled=False)
        # print("Saving profile")
        self.profile["validated"] = True
        del self.profile["picture"]
        response = requests.put("https://airsports.no/api/v1/userprofile/update_profile/",
                                headers={'Authorization': "JWT {}".format(self.user_token)},
                                data=self.profile)
        print(response.status_code)
        print(response.text)
        if response.status_code == 200:
            return True
        return False


def fetch_profile_image_data(image_url) -> bytearray:
    return requests.get(image_url).content


def sign_in_user(email, password):
    user = authenticator.sign_in_with_email_and_password(email, password)
    # print(user)
    user_token = user["idToken"]
    user_account = authenticator.get_account_info(user["idToken"])
    # print(user_account)
    user_account = user_account["users"][0]
    if not user_account["emailVerified"]:
        raise MissingEmailVerificationError("User email is not verified")
    profile = fetch_profile(user)
    if profile is None:
        raise MissingProfileError("Profile for user {} does not exist".format(values["EMAIL"]))
    return user, user_account, user_token, profile


def fetch_profile(user: Dict):
    response = requests.get("https://airsports.no/api/v1/userprofile/retrieve_profile/",
                            headers={'Authorization': "JWT {}".format(user['idToken'])}
                            )
    print(response.status_code)
    print(response.text)
    if response.status_code == 200:
        return response.json()


if __name__ == "__main__":
    user_object = User()
    authentication = [
        [sg.Text("Login or create new account")],
        [sg.Text("Email"), sg.InputText(size=(30, 1), key="EMAIL")],
        [sg.Text("Password"), sg.InputText(size=(30, 1), key="PASSWORD", password_char="*")],
        [sg.Button("Login"), sg.Button("Signup"),
         sg.Button("Resend verification email", key="RESEND_VERIFICATION", disabled=True)],
        [sg.ProgressBar(max_value=3, orientation="h", size=(100, 20), key="LOGIN_PROGRESS")],
        [sg.Button("Start tracking", key="START_TRACKING", disabled=True), sg.Text(size=(20, 1),key='TRANSMIT_TIME')],
        [sg.Button("Stop tracking", key="STOP_TRACKING", disabled=True)],
        # [sg.HSeparator()],
        [sg.Button("Quit")],
    ]
    profile = [
        [sg.Text("First name"), sg.Text(size=(30, 1), key="FIRST_NAME"),
         sg.Button("Update", key="UPDATE_FIRST_NAME", disabled=True)],
        [sg.Text("Last name"), sg.Text(size=(30, 1), key="LAST_NAME"),
         sg.Button("Update", key="UPDATE_LAST_NAME", disabled=True)],
        [sg.Button("Save profile", key="SAVE_PROFILE", disabled=True)],
        # [sg.Image(key="PROFILE_IMAGE", size=(100, 100))]

    ]

    layout = [
        [
            sg.Column(authentication),
            # sg.VSeparator(),
            sg.Column(profile)
        ]
    ]
    window = sg.Window(title="Airsports Live Tracking MSFS2020", layout=layout)  # , margins=(20, 20))
    window.read(timeout=0.1)
    window["RESEND_VERIFICATION"].update(disabled=True)
    window["START_TRACKING"].update(disabled=True)
    window["STOP_TRACKING"].update(disabled=True)
    window["UPDATE_FIRST_NAME"].update(disabled=True)
    window["UPDATE_LAST_NAME"].update(disabled=True)
    window["SAVE_PROFILE"].update(disabled=True)
    progress_bar = window["LOGIN_PROGRESS"]
    profile = None
    user = None
    user_token = None
    # Create an event loop
    while True:
        event, values = window.read()
        # End program if user closes window or
        # presses the OK button
        if event == "Quit" or event == sg.WIN_CLOSED:
            break
        if event == "Login":
            user_object.sign_in(window, values)
        if event == "Signup":
            progress_bar.update_bar(1)
            if user_object.sign_up(window, values):
                progress_bar.update_bar(1)
            else:
                progress_bar.update_bar(0)
        if event == "RESEND_VERIFICATION":
            try:
                authenticator.send_email_verification(user_token)
                sg.popup("Resent verification email")
            except HTTPError as e:
                sg.popup(str(e))
        if event == "UPDATE_FIRST_NAME":
            user_object.profile["first_name"] = sg.popup_get_text("First name", "Please update your first name",
                                                                  default_text=user_object.profile["first_name"])
            window["FIRST_NAME"].update(user_object.profile["first_name"])
            window["SAVE_PROFILE"].update(disabled=False)
        if event == "UPDATE_LAST_NAME":
            user_object.profile["last_name"] = sg.popup_get_text("Last name", "Please update your last name",
                                                                 default_text=user_object.profile["last_name"])
            window["LAST_NAME"].update(user_object.profile["last_name"])
            window["SAVE_PROFILE"].update(disabled=False)
        if event == "SAVE_PROFILE":
            if user_object is not None:
                if user_object.save_profile(window):
                    sg.popup("Success", "Profile saved successfully")
                else:
                    sg.popup("Failure", "Saving user profile failed")
            else:
                sg.popup("Error", "You are not logged in")
        if event == "START_TRACKING":
            if not user_object.profile["validated"]:
                sg.popup("Please update your user profile")
                continue
            if not currently_tracking:
                tracking_event.clear()
                window["START_TRACKING"].update(disabled=True)
                window["STOP_TRACKING"].update(disabled=False)
                threading.Thread(target=run, args=(user_object.profile["simulator_tracking_id"],window["TRANSMIT_TIME"])).start()
            else:
                sg.popup("Still tracking")
        if event == "STOP_TRACKING":
            window["START_TRACKING"].update(disabled=False)
            window["STOP_TRACKING"].update(disabled=True)
            tracking_event.set()

    window.close()
