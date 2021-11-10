import React from "react";
import AirsportsRenderer from "./airsportsRenderer";
import {formatTime} from "../../utilities";
import {divIcon, marker} from "leaflet";

const L = window['L']


export default class AnrCorridorRenderer extends AirsportsRenderer {
    filterWaypoints() {
        return this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return (waypoint.type === 'sp' || waypoint.type==='fp')
        })
    }
}