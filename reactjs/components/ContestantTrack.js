import React, {Component} from "react";
import {connect} from "react-redux";
import {fetchContestantData} from "../actions";
import 'leaflet'
import 'leaflet.markercluster'
import {anomalyAnnotationIcon, informationAnnotationIcon} from "./iconDefinitions";
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"
import {pz} from "../utilities";

const L = window['L']

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestantId]
})

class ConnectedContestantTrack extends Component {
    constructor(props) {
        super(props);
        this.map = props.map
        this.colour = props.colour
        this.contestantNumber = props.contestantNumber
        this.paddedContestantNumber = pz(this.contestantNumber, 2)
        this.contestantName = props.contestantName
        this.contestantId = props.contestantId
        this.markers = L.markerClusterGroup()
        this.lineCollection = null;
        this.dot = null;
        this.annotationLayer = L.layerGroup()
        const size = 24;
        this.airplaneIcon = L.divIcon({
            html: '<i class="fa fa-plane" style="color: ' + this.colour + '"><br/>' + this.paddedContestantNumber + ' ' + this.contestantName + '</i>',
            iconSize: [size, size],
            iconAnchor: [size, size / 2],
            className: "myAirplaneIcon"
        })
        this.iconMap = {
            anomaly: anomalyAnnotationIcon, information: informationAnnotationIcon
        }
        this.fetchNextData()

    }

    fetchNextData() {
        if (this.props.contestantData !== undefined) {
            this.props.fetchContestantData(this.contestantId, new Date(this.props.contestantData.latest_time))
        } else {
            this.props.fetchContestantData(this.contestantId)
        }
        // setTimeout(() => this.fetchNextData(), this.props.fetchInterval)
    }


    componentDidMount() {
    }

    componentDidUpdate(previousProps) {
        if (previousProps.contestantData === undefined || this.props.contestantData.latest_time !== previousProps.contestantData.latest_time) {
            if (this.props.contestantData.positions.length > 0) {
                const positions = this.props.contestantData.positions.map((position) => {
                    return [position.latitude, position.longitude]
                })
                this.renderPositions(positions)
            }
            if (this.props.contestantData.annotations.length > 0) {
                this.renderAnnotations(this.props.contestantData.annotations)
            }
        }
    }

    createLiveEntities(positions) {
        const newest_position = positions.slice(-1)[0];

        this.lineCollection = L.polyline(positions, {
            color: this.colour
        })
        this.dot = L.marker(newest_position, {icon: this.airplaneIcon}).bindTooltip(this.contestantName, {
            permanent: false
        })
        this.showTrack()
    }

    renderAnnotations(annotations) {
        annotations.map((annotation) => {
            this.addAnnotation(annotation.latitude, annotation.longitude, annotation.message, this.iconMap[annotation.type])
        })
    }

    addAnnotation(latitude, longitude, message, icon) {
        if (icon === undefined) icon = informationAnnotationIcon
        this.markers.addLayer(L.marker([latitude, longitude], {icon: icon}).bindTooltip(message, {
            permanent: false
        }))
    }

    showAnnotations() {
        if (!this.displayAnnotations) {
            this.markers.addTo(this.map)
            this.displayAnnotations = true
        }
    }

    hideAnnotations() {
        if (this.displayAnnotations) {
            this.markers.removeFrom(this.map)
            this.displayAnnotations = false
        }
    }

    showTrack() {
        if (!this.displayed && this.dot) {
            this.lineCollection.addTo(this.map)
            this.dot.addTo(this.map)
            this.displayed = true
        }
    }

    hideTrack() {
        if (this.displayed && this.dot) {
            this.lineCollection.removeFrom(this.map)
            this.dot.removeFrom(this.map)
            this.displayed = false
        }
    }

    createPolyline(positions) {
        positions.map((position) => {
            this.lineCollection.addLatLng(position)
        })
    }


    renderPositions(b) {
        if (b.length) {
            if (!this.dot) {
                this.createLiveEntities(b)
            } else {
                this.dot.setLatLng(b.slice(-1)[0])
                b.map((position) => {
                    this.lineCollection.addLatLng(position)
                })
            }
        }
    }

    render() {
        return <div/>;
    }

}

const ContestantTrack = connect(mapStateToProps, {fetchContestantData})(ConnectedContestantTrack);
export default ContestantTrack;