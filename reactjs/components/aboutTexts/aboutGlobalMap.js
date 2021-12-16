import React, {Component} from "react";
import {
    isAndroid,
    isIOS
} from "react-device-detect";
import Icon from "@mdi/react";
import {mdiGoKartTrack} from "@mdi/js";

import {internalColour, ognColour, openSkyColour} from "../aircraft/aircraft";

const aboutGlobalMap = <div>
    <img src={"/static/img/airsports_no_text.png"} style={{float: "right", width: "40px"}} alt={"Global logo"}/>
    <h4>Global map - tracking and events</h4>
    <ul>
        <li>Use Live Tracking to share your position!</li>
        <li>Help yourself and others and be visible on the global map.</li>
        <li>Get an overview of ongoing and upcoming events.</li>
        <li>Clicking on the event, and jump to the event details.</li>
    </ul>
    <p/>
        Map aircraft symbols
        <table className={"table-compact borderless"}>
            <tbody>
            <tr>
                <td style={{width: "300px"}}><i className="mdi mdi-airplanemode-active" style={{color: internalColour}}/> Active aircraft (AirSports)</td>
                <td rowSpan={4} style={{verticalAlign: "top"}}>Speed: GPS in KTS.<br/>Altitude: GPS nearest 100 feet</td>
            </tr>
            <tr>
                <td style={{width: "300px"}}><i className="mdi mdi-airplanemode-active" style={{color: openSkyColour}}/> Active aircraft (OpenSky)</td>
            </tr>
            <tr>
                <td style={{width: "300px"}}><i className="mdi mdi-airplanemode-active" style={{color: ognColour}}/> Active aircraft (OGN)</td>
            </tr>
            <tr>
                <td><i className="mdi mdi-airplanemode-active" style={{color: internalColour, opacity: 0.4}}/> &lt; 40 knots
                </td>
            </tr>
            <tr>
                <td><i className="mdi mdi-airplanemode-active" style={{color: "grey", opacity: 0.4}}/> &gt; 20 sec old
                </td>
            </tr>
            </tbody>
        </table>
        <p/>
        Live Tracking is for entertainment use only! The app requires gps and mobile coverage to work. For more
        information about Air Sports Live Tracking, please see <a href={"https://airsports.no/terms_and_conditions/"}>Terms
        And Conditions</a>.
    <hr/>
    <p/>
        <Icon path={mdiGoKartTrack} title={"Tracking"} size={1.5} color={"#e01b1c"}
              style={{float: "right", width: "50px"}}/>
        <h4>Competition Flying - with real-time scoring</h4>
        With airsports.no you can create competitions like Precision Flying, Rally Flying, or Air Navigation Racing.
        Organizers can use this feature for free, so contact us at
        support[at]airsports.no to become an organizer. The contestants only need the app to compete in the contest, no hardware tracker required.
    <p>
        Take a look at our <a href={"https://youtu.be/4ZPlDVjXabs"}>competition creation tutorial</a>, and
        please visit and subscribe to our YouTube Channel for more videos.
    </p>
    <hr/>
    <p/>
        <img src={"/static/img/airsports_help.png"} style={{float: "right", width: "40px", marginTop: "-10px"}} alt={"Global logo"}/>
        <b>Live Tracking tutorial</b>
        <div className="video-container">
            <iframe src="https://www.youtube.com/embed/UBiX8IQjIHw"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    frameBorder="0" allowFullScreen className="video"/>
        </div>
</div>

export default aboutGlobalMap
