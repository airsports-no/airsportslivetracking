import React, { Component } from "react";
import { circle } from "leaflet";


export default class FreeWaypointRenderer extends Component {
    constructor(props) {
        super(props)
        this.circles = []
    }
    componentDidMount() {
        this.renderFreeWaypoints()
    }

    renderFreeWaypoints() {
        for (const circle of this.circles) {
            circle.removeFrom(this.props.map)
        }
        this.circles = []

        const localRoute = this.props.currentHighlightedContestant ? this.props.contestants[this.props.currentHighlightedContestant].route : this.props.navigationTask.route
        const usedWaypoints = localRoute.waypoints.map((waypoint) => { return waypoint.name })
        const options = { permanent: true, direction: "center", className: "prohibitedTooltip" }
        localRoute.freewaypoint_set.filter((waypoint) => { return !usedWaypoints.includes(waypoint.name) }).map((waypoint) => {
            const c = circle([waypoint.latitude, waypoint.longitude], {
                radius: (waypoint.gateWidth || 1)* 1852 / 2,
                color: 'blue',
                opacity: 0.05
            }).addTo(this.props.map)
            this.circles.push(c)
            c.bindTooltip(waypoint.name, options).openTooltip()
        })

    }

    render() {
        return null
    }

}