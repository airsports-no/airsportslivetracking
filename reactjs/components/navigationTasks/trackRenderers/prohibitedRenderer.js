import React, {Component} from "react";
import {polygon} from "leaflet";


export default class ProhibitedRenderer extends Component {
    componentDidMount() {
        this.renderProhibited()
    }

    renderProhibited() {
        this.props.navigationTask.route.prohibited_set.map((polygonDefinition) => {
            let offset = [0, 0]
            const weight = 1
            if (polygonDefinition.tooltip_position) {
                offset = polygonDefinition.tooltip_position
            }
            const options = {permanent: true, direction: "center", className: "prohibitedTooltip", offset: offset}
            if (polygonDefinition.type === "prohibited") {
                let p = polygon(polygonDefinition.path, {color: "red", weight: weight}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, options).openTooltip()
            } else if (polygonDefinition.type === "penalty") {
                let p = polygon(polygonDefinition.path, {color: "orange", weight: weight}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, options).openTooltip()
            } else if (polygonDefinition.type === "info") {
                let p = polygon(polygonDefinition.path, {color: "lightblue", weight: weight}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, options).openTooltip()
            } else if (polygonDefinition.type === "gate") {
                let p = polygon(polygonDefinition.path, {color: "blue", weight: weight}).addTo(this.props.map)
                p.bindTooltip(polygonDefinition.name, {
                    permanent: false,
                    direction: "center",
                    className: "prohibitedTooltip",
                    offset: offset
                })
            }
        })
    }

    render() {
        return null
    }

}