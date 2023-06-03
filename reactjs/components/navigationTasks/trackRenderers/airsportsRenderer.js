import React from "react";
import {polyline} from "leaflet";
import GenericRenderer from "./genericRenderer";

export default class AirsportsRenderer extends GenericRenderer {
    renderRoute() {
        this.lines = []
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return waypoint.type === 'sp' && waypoint.gate_line_extended
        }).map((gate) => {
            polyline([[gate.gate_line_extended[0][0], gate.gate_line_extended[0][1]], [gate.gate_line_extended[1][0], gate.gate_line_extended[1][1]]], {
                color: "green",
                dashArray: "4 8"
            }).addTo(this.props.map)
        })

        this.filterWaypoints().map((gate) => {
            this.lines.push(polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.props.map))
        })
        let outsideTrack = []
        let insideTrack = []
        for (const waypoint of this.props.navigationTask.route.waypoints) {
            if (waypoint.left_corridor_line) {
                // This is the preferred option, using the gate line is for backwards compatibility
                outsideTrack.push(...waypoint.left_corridor_line)
                insideTrack.push(...waypoint.right_corridor_line)
            } else {
                outsideTrack.push(waypoint.gate_line[0])
                insideTrack.push(waypoint.gate_line[1])
            }
        }
        let route = polyline(insideTrack, {
            color: "blue"
        }).addTo(this.props.map)
        polyline(outsideTrack, {
            color: "blue"
        }).addTo(this.props.map)

        return route
    }

    render() {
        return null
    }

}