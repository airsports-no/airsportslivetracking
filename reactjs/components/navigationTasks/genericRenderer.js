import React, {Component} from "react";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";
import {formatTime} from "../../utilities";

const L = window['L']

function getTextWidth(text, font) {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');

  context.font = font || getComputedStyle(document.body).font;

  return context.measureText(text).width;
}

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

    filterWaypoints() {
        return this.props.navigationTask.route.waypoints.filter((waypoint) => {
            return (waypoint.gate_check || waypoint.time_check) && ((this.props.navigationTask.display_secrets && this.props.displaySecretGates) || waypoint.type !== "secret")
        })
    }

    renderMarkers() {
        for (const marker of this.markers) {
            marker.removeFrom(this.props.map)
        }
        this.markers = []

        const currentContestant = this.props.navigationTask.contestant_set.find((contestant) => {
            return contestant.id === this.props.currentHighlightedContestant
        })
        this.filterWaypoints().map((waypoint) => {
            let waypointText = waypoint.name
            let time
            if (currentContestant) {
                time = new Date(currentContestant.gate_times[waypoint.name])
                waypointText = waypoint.name + " " + formatTime(time)
            }
            const m = marker(waypoint.outer_corner_position[0], {
                color: "blue",
                icon: divIcon({
                    html: '<i>' + waypointText + '</i>',
                    iconSize: [80, 40],
                    className: "myGateLink",
                    iconAnchor: [waypoint.outer_corner_position[1]===1?0:80, waypoint.outer_corner_position[2]===1?0:40]
                })
            }).on('click', () => {
                this.props.handleMapTurningPointClick(waypoint.name)
            }).addTo(this.props.map)
            // if (currentContestant) {
            //     m.bindTooltip(formatTime(time), {
            //         direction: "bottom",
            //         offset: [0,25]
            //         // opacity: 0.5
            //     })
            // }
            this.markers.push(m)
        });
    }


    renderRoute() {
    }

    render() {
        return null
    }

}