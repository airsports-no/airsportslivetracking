import React from "react";
import {polyline} from "leaflet";
import GenericRenderer from "./genericRenderer";

const L = window['L']


export default class PrecisionRenderer extends GenericRenderer {
    renderRoute() {
        for (const line of this.lines) {
            line.removeFrom(this.props.map)
        }
        this.lines = []
        this.filterWaypoints().map((gate) => {
            this.lines.push(polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.props.map))
        })
        let tracks = []
        let currentTrack = []
        const typesToIgnore = ["to", "ldg", "ildg"]
        for (const waypoint of this.props.navigationTask.route.waypoints) {
            if (waypoint.type === 'isp') {
                tracks.push(currentTrack)
                currentTrack = []
            }
            if (!typesToIgnore.includes(waypoint.type)) {
                if (waypoint.is_procedure_turn) {
                    currentTrack.push(...waypoint.procedure_turn_points)
                } else {
                    currentTrack.push([waypoint.latitude, waypoint.longitude])
                }
            }
        }
        tracks.push(currentTrack)
        // let turningPoints = this.props.navigationTask.route.waypoints.filter((waypoint) => {
        //     return true //waypoint.type === "tp"
        // }).map((waypoint) => {
        //     return [waypoint.latitude, waypoint.longitude]
        // });

        // this.props.navigationTask.route.waypoints.filter((waypoint) => {
        //     return waypoint.is_procedure_turn
        // }).map((waypoint) => {
        //     circle([waypoint.latitude, waypoint.longitude], {
        //         radius: 500,
        //         color: "blue"
        //     }).addTo(this.props.map)
        // })
        // Temporarily plot range circles
        // this.props.navigationTask.track.waypoints.map((waypoint) => {
        //     circle([waypoint.latitude, waypoint.longitude], {
        //         radius: waypoint.insideDistance,
        //         color: "orange"
        //     }).addTo(this.props.map)
        // })
        // Plot starting line
        // const gate = this.props.navigationTask.track.starting_line
        // polyline([[gate.gate_line[1], gate.gate_line[0]], [gate.gate_line[3], gate.gate_line[2]]], {
        //             color: "red"
        //         }).addTo(this.props.map)
        let route;
        for (const track of tracks) {
            route = polyline(track, {
                color: "blue"
            }).addTo(this.props.map)
            this.lines.push(route)
        }
        this.props.map.fitBounds(route.getBounds(), {padding: [50, 50]})


    }

    render() {
        return null
    }

}