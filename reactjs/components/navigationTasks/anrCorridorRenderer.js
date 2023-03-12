import React from "react";
import AirsportsRenderer from "./airsportsRenderer";

export default class AnrCorridorRenderer extends AirsportsRenderer {
    filterWaypoints() {
        return this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return (waypoint.type === 'sp' || waypoint.type==='fp')
        })
    }
}