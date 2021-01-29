import React, {Component} from "react";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";

const L = window['L']


export default class AnrCorridorRenderer extends Component {
    componentDidMount() {
        this.renderRoute()
    }

    renderRoute() {
        this.props.navigationTask.route.waypoints.map((gate) => {
            if (["sp", "fp"].includes(gate.type)) {
                polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                    color: "blue"
                }).addTo(this.props.map)
            }
        })
        let outsideTrack = []
        let insideTrack = []
        for (const waypoint of this.props.navigationTask.route.waypoints) {
            if (this.props.navigationTask.route.rounded_corners && waypoint.left_corridor_line) {
                outsideTrack.push(...waypoint.left_corridor_line)
                insideTrack.push(...waypoint.right_corridor_line)
            } else {
                outsideTrack.push(waypoint.gate_line[0])
                insideTrack.push(waypoint.gate_line[1])
            }
        }
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return waypoint.gate_check || waypoint.time_check
        }).map((waypoint) => {
            marker([waypoint.latitude, waypoint.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + waypoint.name + '</i>',
                    iconSize: [20, 20],
                    className: "myGateIcon"
                })
            }).on('click', () => {
                this.handleMapTurningPointClick(waypoint.name)
            }).addTo(this.props.map)
        });
        let route = polyline(insideTrack, {
            color: "blue"
        }).addTo(this.props.map)
        polyline(outsideTrack, {
            color: "blue"
        }).addTo(this.props.map)

        this.props.map.fitBounds(route.getBounds(), {padding: [50, 50]})

    }

    render() {
        return null
    }

}