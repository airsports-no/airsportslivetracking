import React, {Component} from "react";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";
import {formatTime} from "../../utilities";

const L = window['L']


export default class GenericRenderer extends Component {
    constructor(props) {
        super(props)
        this.markers = []
        this.lines = []
    }

    componentDidMount() {
        this.markers = []
        this.lines = []
        this.renderRoute()
        this.renderMarkers()
    }

    componentDidUpdate(prevProps, prevState) {
        // this.renderRoute()
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
            return (waypoint.gate_check || waypoint.time_check) && ((this.props.navigationTask.display_secrets && this.props.displaySecretGates) || waypoint.type !== "secret")
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
    }

    render() {
        return null
    }

}