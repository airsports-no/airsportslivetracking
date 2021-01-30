import React, {Component} from "react";
import {polygon} from "leaflet";


export default class ProhibitedRenderer extends Component {
    componentDidMount() {
        this.renderProhibited()
    }

    renderProhibited() {
        this.props.navigationTask.route.prohibited_set.map((polygonDefinition) => {
            let p = polygon(polygonDefinition.path, {color: "red"}).addTo(this.props.map)
            p.bindTooltip(polygonDefinition.name, {permanent: true, direction: "center"}).openTooltip()
        })
    }

    render() {
        return null
    }

}