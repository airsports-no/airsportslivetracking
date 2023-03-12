import React, {Component} from "react";
import {polyline} from "leaflet";

export default class LandingRenderer extends Component {
    componentDidMount() {
        this.renderRoute()
    }

    renderRoute() {
        const gate = this.props.navigationTask.route.landing_gate
        const line = polyline([[gate.gate_line[0][0], gate.gate_line[0][1]], [gate.gate_line[1][0], gate.gate_line[1][1]]], {
            color: "blue"
        }).addTo(this.props.map)
        this.props.map.fitBounds(line.getBounds(), {padding: [50, 50]})
        this.props.map.zoomOut(4)
    }

    render() {
        return null
    }

}