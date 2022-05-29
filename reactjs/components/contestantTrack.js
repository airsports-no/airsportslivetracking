import React, {Component} from "react";
import {connect} from "react-redux";
// import {renderToString} from 'react-dom/server';
import {
    displayAllTracks,
    displayOnlyContestantTrack, hideLowerThirds,
    highlightContestantTable, highlightContestantTrack, initialLoading,
    initialLoadingComplete, removeHighlightContestantTable, removeHighlightContestantTrack, setDisplay, showLowerThirds
} from "../actions";
import 'leaflet'
import 'leaflet.markercluster'
import {anomalyAnnotationIcon, informationAnnotationIcon} from "./iconDefinitions";
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"
import {contestantLongForm, contestantShortForm, getBearing} from "../utilities";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY} from "../constants/display-types";

const L = window['L']

const mapStateToProps = (state, props) => ({
    explicitlyDisplayAllTracks: state.explicitlyDisplayAllTracks,
    contestantData: state.contestantData[props.contestant.id],
    displayTracks: state.displayTracks,
    isInitialLoading: state.initialLoadingContestantData[props.contestant.id],
    dim: state.highlightContestantTrack.length > 0 && !state.highlightContestantTrack.includes(props.contestant.id),
    highlight: state.highlightContestantTrack.length > 0 && state.highlightContestantTrack.includes(props.contestant.id),
})

class ConnectedContestantTrack extends Component {
    constructor(props) {
        super(props);
        this.trailLength = 120
        this.map = props.map
        this.contestant = props.contestant
        this.markers = L.markerClusterGroup()
        this.partialTrack = null;
        this.fullTrack = null;
        // this.allPoints = []
        this.partialPoints = []
        this.dot = null;
        this.dotText = null;
        this.previousLastTime = null;
        this.lastNewData = null;
        this.shortTrackDisplayed = false
        this.fullTrackDisplayed = false
        this.lastPositionTime = null

        this.annotationLayer = L.layerGroup()
        this.iconMap = {
            anomaly: anomalyAnnotationIcon, information: informationAnnotationIcon
        }
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
        this.bearing = 0
    }

    createAirplaneIcon() {
        const size = 36;
        const big = "m 10.090825,3.1817631 c 0.08861,6e-7 0.140999,0.060929 0.318507,0.5444019 0.02095,0.057066 0.06325,0.3004376 0.06325,0.3004376 -10e-7,0 0.141832,0.00678 0.178455,0.00678 0.0708,2.7e-6 0.166559,0.06313 0.214599,0.1400528 0.149043,0.2386617 0.381759,1.5521712 0.381759,2.1572766 0,0.3755102 0.03146,0.6005683 0.09036,0.6460538 0.0497,0.038385 0.310305,0.1567215 0.578286,0.2620358 0.472843,0.1858249 0.591384,0.1968549 4.011859,0.3795011 2.7087,0.1446399 3.561359,0.2127399 3.688831,0.29366 0.353446,0.2243698 0.371848,0.7427586 0.06099,1.7235632 l -0.160385,0.5060001 c 0,0 -8.337706,1.380206 -8.337706,1.380206 l -0.700268,5.12551 0.185231,0.05196 c 0.101819,0.02819 0.785824,0.103407 1.52026,0.16716 0.734436,0.06375 1.376875,0.149876 1.427643,0.19201 0.204091,0.16938 0.04371,1.504447 -0.180715,1.504446 -0.354211,1e-6 -1.663847,0.176113 -1.732597,0.23267 -0.04908,0.04039 -1.174574,0.19201 -1.608358,0.192009 -0.4337829,10e-7 -1.5592721,-0.151628 -1.6083567,-0.192009 -0.068753,-0.05656 -1.3783873,-0.232669 -1.7325993,-0.23267 -0.2244224,0 -0.3848053,-1.335066 -0.180713,-1.504446 0.05079,-0.04211 0.6932051,-0.128254 1.4276415,-0.19201 0.7344359,-0.06375 1.4184429,-0.138971 1.5202606,-0.167161 l 0.1852326,-0.05196 -0.7002677,-5.12551 c 0,0 -8.33770758,-1.380207 -8.33770823,-1.380206 L 0.50393175,9.6355217 C 0.19307535,8.6547166 0.21147862,8.1363305 0.56492244,7.9119593 0.6923954,7.8310385 1.5450527,7.7629376 4.2537528,7.6182985 7.6742292,7.4356511 7.7927689,7.424622 8.2656101,7.2387991 8.5335918,7.1334836 8.794199,7.015146 8.8438974,6.9767629 8.902787,6.9312768 8.934252,6.7062189 8.9342539,6.3307088 8.9342528,5.7256033 9.166967,4.4120912 9.316013,4.1734318 9.3640494,4.0965093 9.4598038,4.0333761 9.5306106,4.0333781 c 0.036626,-2.6e-6 0.1761975,-0.00678 0.1761975,-0.00678 0,0 0.042298,-0.2433728 0.06325,-0.300437 C 9.9475664,3.242691 10.002216,3.1817618 10.090826,3.1817618 Z"
        const little = "m 10.064097,4.1525362 c 0.07829,6e-7 0.124587,0.053837 0.281433,0.4810336 0.01851,0.050423 0.05588,0.2654666 0.05588,0.2654666 -1e-6,0 0.125323,0.00599 0.157682,0.00599 0.06256,2.4e-6 0.147172,0.055782 0.18962,0.1237507 0.131695,0.2108815 0.337323,1.3714984 0.337323,1.9061696 0,0.3318007 0.0278,0.5306621 0.07984,0.5708531 0.04392,0.033917 0.274186,0.1384791 0.510974,0.2315348 0.417805,0.1641949 0.522547,0.173941 3.544879,0.3353272 2.393407,0.1278038 3.146817,0.187977 3.259451,0.259478 0.312305,0.1982531 0.328565,0.6563015 0.05389,1.5229404 l -0.141716,0.4471018 c 0,0 -7.367196,1.21955 -7.367196,1.21955 l -0.618757,4.528901 0.16367,0.04591 c 0.08997,0.02491 0.694354,0.09137 1.343301,0.147702 0.648948,0.05632 1.216607,0.132431 1.261466,0.16966 0.180334,0.149665 0.03863,1.32933 -0.15968,1.329329 -0.312981,10e-7 -1.470175,0.155614 -1.530922,0.205587 -0.04337,0.03569 -1.037854,0.16966 -1.421146,0.169659 -0.3832901,10e-7 -1.3777725,-0.133978 -1.4211431,-0.169659 -0.060752,-0.04998 -1.217943,-0.205586 -1.5309244,-0.205587 -0.1982996,0 -0.340014,-1.179664 -0.1596788,-1.329329 0.044876,-0.03721 0.6125162,-0.113324 1.261464,-0.16966 0.6489488,-0.05632 1.2533368,-0.122795 1.3433023,-0.147703 L 9.7207809,16.050632 9.102024,11.521731 c 0,0 -7.3671983,-1.219551 -7.3671983,-1.21955 L 1.5931192,9.8550773 C 1.3184465,8.988438 1.3347076,8.5303919 1.6470103,8.3321376 1.7596458,8.260636 2.513053,8.200462 4.9064613,8.0726589 7.9287935,7.9112716 8.0335358,7.9015264 8.4513376,7.7373332 8.6881264,7.644276 8.9183991,7.5397133 8.9623131,7.505798 c 0.052038,-0.040191 0.079834,-0.2390527 0.079844,-0.5708534 -9e-7,-0.5346712 0.205625,-1.6952905 0.3373228,-1.9061699 0.04245,-0.067969 0.1270532,-0.1237532 0.1896187,-0.1237515 0.032364,-2.3e-6 0.1556875,-0.00599 0.1556875,-0.00599 0,0 0.037374,-0.2150441 0.055892,-0.2654661 0.1568465,-0.427192 0.2051343,-0.481029 0.2834299,-0.481029 z"
        const solidPath = '<path style="fill:' + this.props.colour + ';stroke-width:0.8742;" d="' + little + '"/>'
        const outlinePath = '<path style="fill:black;stroke-width:0.93;" d="' + big + '"/>'
        return L.divIcon({
            // html: '<i class="mdi mdi-airplanemode-active" style="color: ' + this.props.colour + '; transform: rotate(' + this.bearing + 'deg); width: {size}"><br/>' + contestantShortForm(this.props.contestant) + '</i>',
            // html: '<i class="mdi mdi-airplanemode-active" style="color: ' + this.props.colour + '; transform: rotate(' + this.bearing + 'deg); font-size: ' + size + 'px"/>',
            html: '<svg style="width: ' + size + 'px; transform: rotate(' + this.bearing + 'deg);" x="0px" y="0px" viewBox="0 0 20 20">' + outlinePath + solidPath + '</svg>',
            // iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })

    }


    createAirplaneTextIcon() {
        const size = 20;
        const style = {
            color: this.props.colour,
            fontSize: size + 'px'
        }
        const text = <div style={style}>contestantShortForm(this.props.contestant)</div>
        const length = Math.ceil(text.clientWidth)
        return L.divIcon({
            html: '<div style="color: ' + this.props.colour + '; font-size: ' + size + 'px">' + contestantShortForm(this.props.contestant) + '</div>',
            iconAnchor: [100, -16],
            iconSize: [200, size],
            className: "myAirplaneTextIcon text-center"
        })

    }

    handleContestantLinkClick(e, contestantId) {
        L.DomEvent.stopPropagation(e)
        this.props.setDisplay({displayType: CONTESTANT_DETAILS_DISPLAY, contestantId: contestantId})
        this.props.displayOnlyContestantTrack(contestantId)
        this.props.showLowerThirds(contestantId)
    }

    resetToAllContestants() {
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }


    componentDidMount() {
    }

    componentWillUnmount() {
        this.hideTrack()
        this.hideAnnotations()
        if (this.props.highlight || this.props.displayTracks.includes(this.props.contestant.id)) {
            this.resetToAllContestants()
        }
    }

    componentDidUpdate(previousProps) {
        if (this.fullTrack && this.dot) {
            if (this.props.colour !== previousProps.colour) {
                this.updateStyle()
            }
        }
        const displayTracks = this.props.displayTracks;
        if (this.props.displayMap) {
            if (this.props.contestantData !== undefined) {
                if (this.props.contestantData.positions && this.props.contestantData.positions.length > 0) {
                    // this.props.contestantData.positions.map((position) => {
                    //     console.log(new Date() + "Received position ID " + position.position_id + " for device ID " + position.device_id)
                    // })
                    const p = this.props.contestantData.positions.map((position) => {
                        return {
                            latitude: position.latitude,
                            longitude: position.longitude,
                            time: new Date(position.time)
                        }
                    }).filter((pos) => {
                        return !this.lastPositionTime || pos.time > this.lastPositionTime
                    })
                    if (p.length > 0) {
                        this.lastPositionTime = p.slice(-1)[0].time
                    }
                    // this.allPoints.push(...p)
                    this.partialPoints.push(...p)
                    const positions = p.map((position) => {
                        return [position.latitude, position.longitude]
                    })
                    this.renderPositions(positions)
                }
                if (this.props.contestantData.annotations) {
                    this.renderAnnotations(this.props.contestantData.annotations)
                }
                if (!displayTracks) {
                    if (this.props.highlight) {
                        this.showFullTrack()
                    } else {
                        this.showTrack()
                    }
                    this.hideAnnotations()
                } else {
                    if (displayTracks.includes(this.contestant.id)) {
                        this.showFullTrack()
                        if (displayTracks.length === 1) {
                            this.showAnnotations()
                        }
                    } else {
                        this.hideTrack()
                        this.hideAnnotations()
                    }
                }
            }
        }
    }

    updateStyle() {
        this.fullTrack.setStyle({
            color: this.props.colour,
            opacity: 1,
            weight: 3
        })
        this.partialTrack.setStyle({
            color: this.props.colour,
            opacity: 1,
            weight: 3
        })
        this.dot.setIcon(this.createAirplaneIcon())
        this.dotText.setIcon(this.createAirplaneTextIcon())
    }

    normal() {
        // this.fullTrack.setStyle({
        //     color: this.props.colour,
        //     opacity: 1,
        //     weight: 3
        // })
    }


    highlight() {
        // this.fullTrack.setStyle({
        //     color: this.props.colour,
        //     opacity: 1,
        //     weight: 6
        // })
    }

    dim() {
        // this.fullTrack.setStyle({
        //     color: this.props.colour,
        //     opacity: 0.2,
        //     weight: 1
        // })
    }

    createLiveEntities(positions) {
        const newest_position = positions.slice(-1)[0];
        this.partialTrack = L.polyline([newest_position], {
            color: this.props.colour,
            opacity: 1,
            weight: 3
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) => {
                this.props.highlightContestantTable(this.contestant.id)
                this.props.highlightContestantTrack(this.contestant.id)
            }
        ).on('mouseout', (e) => {
                this.props.removeHighlightContestantTable(this.contestant.id)
                this.props.removeHighlightContestantTrack(this.contestant.id)
            }
        )
        this.fullTrack = L.polyline(positions, {
            color: this.props.colour,
            opacity: 1,
            weight: 3
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) => {
                // this.props.highlightContestantTable(this.contestant.id)
                this.props.highlightContestantTrack(this.contestant.id)
            }
        ).on('mouseout', (e) => {
                // this.props.removeHighlightContestantTable(this.contestant.id)
                this.props.removeHighlightContestantTrack(this.contestant.id)
            }
        )
        this.dot = L.marker(newest_position, {icon: this.createAirplaneIcon()}).bindTooltip(contestantLongForm(this.contestant), {
            permanent: false
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) => {
                // this.props.highlightContestantTable(this.contestant.id)
                this.props.highlightContestantTrack(this.contestant.id)
            }
        ).on('mouseout', (e) => {
                // this.props.removeHighlightContestantTable(this.contestant.id)
                this.props.removeHighlightContestantTrack(this.contestant.id)
            }
        )
        this.dotText = L.marker(newest_position, {icon: this.createAirplaneTextIcon()}).bindTooltip(contestantLongForm(this.contestant), {
            permanent: false
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) => {
                // this.props.highlightContestantTable(this.contestant.id)
                this.props.highlightContestantTrack(this.contestant.id)
            }
        ).on('mouseout', (e) => {
                // this.props.removeHighlightContestantTable(this.contestant.id)
                this.props.removeHighlightContestantTrack(this.contestant.id)
            }
        )
    }

    clearAnnotations() {
        this.markers.eachLayer((l) => {
            this.markers.removeLayer(l)
        })
    }

    renderAnnotations(annotations) {
        this.clearAnnotations()
        annotations.filter((annotation) => {
            return this.props.navigationTask.display_secrets || annotation.gate_type !== "secret"
        }).map((annotation) => {
            this.addAnnotation(annotation.latitude, annotation.longitude, annotation.message, this.iconMap[annotation.type])
        })
    }

    addAnnotation(latitude, longitude, message, icon) {
        if (icon === undefined) icon = informationAnnotationIcon
        this.markers.addLayer(L.marker([latitude, longitude], {icon: icon}).bindTooltip(message.replace("\n", "<br/>"), {
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

    showFullTrack() {
        if (this.dot && (!this.fullTrackDisplayed || this.shortTrackDisplayed)) {
            this.fullTrack.addTo(this.map)
            this.partialTrack.removeFrom(this.map)
            this.dot.addTo(this.map)
            this.dotText.addTo(this.map)
            this.fullTrackDisplayed = true
            this.shortTrackDisplayed = false
        }
    }

    showTrack() {
        if (this.dot && (!this.shortTrackDisplayed || this.fullTrackDisplayed)) {
            this.fullTrack.removeFrom(this.map)
            this.partialTrack.addTo(this.map)
            this.dot.addTo(this.map)
            this.dotText.addTo(this.map)
            this.shortTrackDisplayed = true
            this.fullTrackDisplayed = false
        }
    }

    hideTrack() {
        if (this.dot && (this.shortTrackDisplayed || this.fullTrackDisplayed)) {
            this.fullTrack.removeFrom(this.map)
            this.partialTrack.removeFrom(this.map)
            this.dot.removeFrom(this.map)
            this.dotText.removeFrom(this.map)
            this.shortTrackDisplayed = false
            this.fullTrackDisplayed = false
        }
    }


    updateBearing() {
        if (this.partialTrack) {
            const positions = this.partialTrack.getLatLngs()
            if (positions.length > 1) {
                const slice = positions.slice(-2)
                this.bearing = getBearing(slice[0].lat, slice[0].lng, slice[1].lat, slice[1].lng)

            }
        }
        this.dot.setIcon(this.createAirplaneIcon())
    }

    trimPartialTrack() {
        if (this.partialTrack) {
            const latestTime = this.partialPoints[this.partialPoints.length - 1].time.getTime()
            this.partialPoints = this.partialPoints.filter((position) => {
                return latestTime - position.time.getTime() < this.trailLength * 1000
            })
            const partial = this.partialPoints.map((position) => {
                return [position.latitude, position.longitude]
            })
            if (partial.length > 0) {
                this.partialTrack.setLatLngs(partial)
                // this.partialTrack.redraw()
            }
        }
    }

    renderPositions(b) {
        if (b.length) {
            if (!this.dot) {
                this.createLiveEntities(b)
            } else {
                const s = b.slice(-1)[0]
                if (s) {
                    this.dot.setLatLng(b.slice(-1)[0])
                    this.dotText.setLatLng(b.slice(-1)[0])
                }
                b.map((position) => {
                    this.fullTrack.addLatLng(position)
                })
            }
            this.trimPartialTrack()
            this.updateBearing()
        }
    }

    render() {
        return null;
    }

}

const ContestantTrack = connect(mapStateToProps, {

    initialLoading,
    initialLoadingComplete,
    setDisplay,
    displayOnlyContestantTrack,
    showLowerThirds,
    highlightContestantTable,
    removeHighlightContestantTable,
    highlightContestantTrack,
    removeHighlightContestantTrack,
    displayAllTracks,
    hideLowerThirds
})(ConnectedContestantTrack);
export default ContestantTrack;