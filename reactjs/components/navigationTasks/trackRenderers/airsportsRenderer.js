import React from "react";
import {polyline} from "leaflet";
import GenericRenderer from "./genericRenderer";

export default class AirsportsRenderer extends GenericRenderer {
    renderRoute() {
        for (const line of this.lines) {
            if (line) {
                line.removeFrom(this.props.map)
            }
        }
        this.lines = []
        let polygon = [this.props.navigationTask.route.corridor_polygon.map((point, index) => {
            return [point.lat, point.lng]
        })];
        polygon.push(polygon[0]) // close the polygon

        //  Air sports  race and challenge does not penalise crossing the extended starting line backwards.
        // this.props.navigationTask.route.waypoints.filter((waypoint) => {
        //     return waypoint.type === 'sp' && waypoint.gate_line_extended
        // }).map((gate) => {
        //     polyline([[gate.gate_line_extended[0][0], gate.gate_line_extended[0][1]], [gate.gate_line_extended[1][0], gate.gate_line_extended[1][1]]], {
        //         color: "green",
        //         dashArray: "4 8"
        //     }).addTo(this.props.map)
        // })

        this.filterWaypoints().map((gate) => {
            this.lines.push(polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.props.map))
        })


        let route = polyline(polygon, {
            color: "blue"
        }).addTo(this.props.map)
        return route
    }

    render() {
        return null
    }

}