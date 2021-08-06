import React, {Component} from "react";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";
import {formatTime} from "../../utilities";

const L = window['L']


export default class PrecisionRenderer extends Component {
    componentDidMount() {
        this.markers = []
        this.lines=[]
        this.renderRoute()
        this.renderMarkers()
    }

    componentDidUpdate(prevProps, prevState) {
        this.renderRoute()
        this.renderMarkers()
    }

    renderMarkers() {
        for (const marker of this.markers) {
            marker.removeFrom(this.props.map)
        }
        this.markers = []

        const currentContestant = this.props.navigationTask.contestant_set.find((contestant) => {
            return contestant.id === this.props.currentHighlightedContestant
        })
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return (waypoint.gate_check || waypoint.time_check) && ((this.props.navigationTask.display_secrets && this.props.displaySecretGates) || waypoint.type!=="secret")
        }).map((waypoint) => {
            let waypointText = waypoint.name

            if (currentContestant) {
                const time = new Date(currentContestant.gate_times[waypoint.name])
                waypointText = waypoint.name + "<br/>" + formatTime(time)
            }
            const m = marker([waypoint.latitude, waypoint.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + waypointText + '</i>',
                    iconSize: [60, 20],
                    className: "myGateIcon"
                })
            }).on('click', () => {
                this.props.handleMapTurningPointClick(waypoint.name)
            }).addTo(this.props.map)
            this.markers.push(m)
        });
    }

    renderRoute() {
        for (const line of this.lines) {
            line.removeFrom(this.props.map)
        }
        this.lines = []
        this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return (waypoint.gate_check || waypoint.time_check) && ((this.props.navigationTask.display_secrets && this.props.displaySecretGates) || waypoint.type!=="secret")
        }).map((gate) => {
            this.lines.push(polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
                color: "blue"
            }).addTo(this.props.map))
            // }
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