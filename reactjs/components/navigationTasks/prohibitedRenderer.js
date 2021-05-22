import React, {Component} from "react";
import {polygon} from "leaflet";


export default class ProhibitedRenderer extends Component {
    componentDidMount() {
        this.renderProhibited()
    }

    renderProhibited() {
        this.props.navigationTask.route.prohibited_set.map((polygonDefinition) => {
            if (polygonDefinition.type === "prohibited") {
                let p = polygon(polygonDefinition.path, {color: "red"}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, {permanent: true, direction: "center", className: "prohibitedTooltip"}).openTooltip()
            } else if (polygonDefinition.type === "info") {
                let p = polygon(polygonDefinition.path, {color: "orange"}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, {permanent: true, direction: "center", className: "prohibitedTooltip"}).openTooltip()
            } else if (polygonDefinition.type === "gate") {
                let p = polygon(polygonDefinition.path, {color: "blue"}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, {permanent: false, direction: "center", className: "prohibitedTooltip"})
            }
        })
    }

    render() {
        return null
    }

}