import React from "react";
import {polyline} from "leaflet";
import GenericRenderer from "./genericRenderer";

export default class PrecisionRenderer extends GenericRenderer {
    renderRoute() {
        const localRoute=this.props.currentHighlightedContestant?this.props.contestants[this.props.currentHighlightedContestant].route:this.props.navigationTask.route
        for (const line of this.lines) {
            line.removeFrom(this.props.map)
        }
        this.lines = []
        localRoute.waypoints.filter((waypoint) => {
            return waypoint.type === 'sp' && waypoint.gate_line_extended
        }).map((gate) => {
            const extendedGate=polyline([[gate.gate_line_extended[0][0], gate.gate_line_extended[0][1]], [gate.gate_line_extended[1][0], gate.gate_line_extended[1][1]]], {
                color: "blue",
                dashArray: "4 8"
            }).addTo(this.props.map)
            this.lines.push(extendedGate)
        })
        this.filterWaypoints().map((gate) => {
            this.lines.push(polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.props.map))
        })
        let tracks = []
        let currentTrack = []
        const typesToIgnore = ["to", "ldg", "ildg", "dummy"]
        let dummyLegs = []
        let currentDummy = []
        let previousWaypoint = null
        for (const waypoint of localRoute.waypoints) {
            if (waypoint.type === 'isp') {
                tracks.push(currentTrack)
                currentTrack = []
            }
            if (waypoint.type !== "dummy") {
                if (previousWaypoint && previousWaypoint.type === "dummy") {
                    dummyLegs.push(currentDummy)
                    currentDummy = []
                }
            } else {
                if (previousWaypoint && previousWaypoint.type !== "dummy") {
                    currentDummy.push([previousWaypoint.latitude, previousWaypoint.longitude])
                }
                currentDummy.push([waypoint.latitude, waypoint.longitude])
            }
            if (!typesToIgnore.includes(waypoint.type)) {
                if (waypoint.is_procedure_turn) {
                    currentTrack.push(...waypoint.procedure_turn_points)
                } else {
                    currentTrack.push([waypoint.latitude, waypoint.longitude])
                }
            }
            previousWaypoint = waypoint
        }
        tracks.push(currentTrack)
        for (const dummy of dummyLegs) {
            this.lines.push(polyline(dummy, {
                color: "pink"
            }).addTo(this.props.map))
        }

        let route;
        for (const track of tracks) {
            route = polyline(track, {
                color: "blue"
            }).addTo(this.props.map)
            this.lines.push(route)
        }

        return route
    }

    render() {
        return null
    }

}