import React, {Component} from "react";
import {connect} from "react-redux";
// import {renderToString} from 'react-dom/server';
import {
    displayOnlyContestantTrack,
    fetchContestantData, highlightContestantTable, initialLoading,
    initialLoadingComplete, removeHighlightContestantTable, setDisplay, showLowerThirds
} from "../actions";
import 'leaflet'
import 'leaflet.markercluster'
import {anomalyAnnotationIcon, informationAnnotationIcon} from "./iconDefinitions";
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"
import {contestantLongForm, contestantShortForm, getBearing} from "../utilities";
import {CONTESTANT_DETAILS_DISPLAY} from "../constants/display-types";

const L = window['L']

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestant.id],
    displayTracks: state.displayTracks,
    isFetching: state.isFetchingContestantData[props.contestant.id],
    initialLoading: state.initialLoadingContestantData[props.contestant.id],
    dim: state.highlightContestantTrack.length > 0 && !state.highlightContestantTrack.includes(props.contestant.id),
    highlight: state.highlightContestantTrack.length > 0 && state.highlightContestantTrack.includes(props.contestant.id),
})

class ConnectedContestantTrack extends Component {
    constructor(props) {
        super(props);
        this.map = props.map
        this.contestant = props.contestant
        this.markers = L.markerClusterGroup()
        this.lineCollection = null;
        this.dot = null;
        this.dotText = null;
        this.previousLastTime = null;
        this.lastNewData = null;
        this.annotationLayer = L.layerGroup()
        this.iconMap = {
            anomaly: anomalyAnnotationIcon, information: informationAnnotationIcon
        }
        this.props.initialLoading(this.contestant.id)
        // this.fetchNextData(false)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
        this.bearing = 0
    }

    createAirplaneIcon() {
        const size = 32;
        return L.divIcon({
            // html: '<i class="mdi mdi-airplanemode-active" style="color: ' + this.props.colour + '; transform: rotate(' + this.bearing + 'deg); width: {size}"><br/>' + contestantShortForm(this.props.contestant) + '</i>',
            html: '<i class="mdi mdi-airplanemode-active" style="color: ' + this.props.colour + '; transform: rotate(' + this.bearing + 'deg); font-size: ' + size + 'px"/>',
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


    // fetchNextData(scheduleNext) {
    //     const finishedByTime = new Date(this.props.contestant.finished_by_time)
    //     let latestTime = null;
    //     if (!this.props.isFetching) {
    //         if (this.props.contestantData !== undefined) {
    //             latestTime = new Date(this.props.contestantData.latest_time)
    //             this.props.fetchContestantData(this.props.contestId, this.props.navigationTaskId, this.contestant.id, latestTime)
    //         } else {
    //             this.props.fetchContestantData(this.props.contestId, this.props.navigationTaskId, this.contestant.id)
    //         }
    //     }
    //     // This must be done second so that we at least fetched data once
    //     const now = new Date()
    //     if (now > finishedByTime && this.lastNewData && (now.getTime() - this.lastNewData.getTime() > 300 * 1000)) {
    //         console.log("Stop fetching contestant " + this.contestant.contestant_number)
    //     } else {
    //         if (scheduleNext) {
    //             this.timeout = setTimeout(() => this.fetchNextData(true), this.props.fetchInterval)// / 2 + Math.random() * this.props.fetchInterval)
    //         }
    //     }
    // }


    componentDidMount() {
    }

    componentWillUnmount() {
        // clearTimeout(this.timeout)
    }

    componentDidUpdate(previousProps) {
        if (this.lineCollection && this.dot) {
            if (this.props.colour !== previousProps.colour) {
                this.updateStyle()
            }
            if (this.props.dim) {
                this.dim()
            } else if (this.props.highlight) {
                this.highlight()
            } else {
                this.normal()
            }
        }
        // if (this.props.contestantData !== undefined) {
        //     if (previousProps.contestantData === undefined || this.props.contestantData.latest_time !== previousProps.contestantData.latest_time) {
        //         this.lastNewData = new Date();
        //     }
        // }
        let finishedInitialLoading = true;
        const displayTracks = this.props.displayTracks;
        if (this.props.contestantData !== undefined) {
            if (previousProps.contestantData === undefined || this.props.contestantData.latest_time !== previousProps.contestantData.latest_time) {
                // if (this.props.contestantData.more_data) {
                // clearTimeout(this.timeout)
                // this.fetchNextData(false)
                // finishedInitialLoading = false;
                // } else if (this.props.initialLoading) {
                // clearTimeout(this.timeout)
                // this.timeout = setTimeout(() => this.fetchNextData(true), this.props.fetchInterval)
                this.props.initialLoadingComplete(this.contestant.id);
                // }
            }
        }
        if (this.props.displayMap) {
            if (this.props.contestantData !== undefined) {
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
                if (finishedInitialLoading) {
                    if (!displayTracks) {
                        this.showTrack()
                        this.hideAnnotations()
                    } else {
                        if (displayTracks.includes(this.contestant.id)) {
                            this.showTrack()
                            this.showAnnotations()
                        } else {
                            this.hideTrack()
                            this.hideAnnotations()
                        }
                    }
                }
            }
        }
    }

    updateStyle() {
        this.lineCollection.setStyle({
            color: this.props.colour,
            opacity: 1,
            weight: 3
        })
        this.dot.setIcon(this.createAirplaneIcon())
        this.dotText.setIcon(this.createAirplaneTextIcon())
    }

    normal() {
        this.lineCollection.setStyle({
            color: this.props.colour,
            opacity: 1,
            weight: 3
        })
    }


    highlight() {
        this.lineCollection.setStyle({
            color: "red",
            opacity: 1,
            weight: 6
        })
    }

    dim() {
        this.lineCollection.setStyle({
            color: this.props.colour,
            opacity: 0.2,
            weight: 1
        })
    }

    createLiveEntities(positions) {
        const newest_position = positions.slice(-1)[0];

        this.lineCollection = L.polyline(positions, {
            color: this.colour
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) =>
            this.props.highlightContestantTable(this.contestant.id)
        ).on('mouseout', (e) =>
            this.props.removeHighlightContestantTable(this.contestant.id)
        )
        this.dot = L.marker(newest_position, {icon: this.createAirplaneIcon()}).bindTooltip(contestantLongForm(this.contestant), {
            permanent: false
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) =>
            this.props.highlightContestantTable(this.contestant.id)
        ).on('mouseout', (e) =>
            this.props.removeHighlightContestantTable(this.contestant.id)
        )
        this.dotText = L.marker(newest_position, {icon: this.createAirplaneTextIcon()}).bindTooltip(contestantLongForm(this.contestant), {
            permanent: false
        }).on('click', (e) =>
            this.handleContestantLinkClick(e, this.contestant.id)
        ).on('mouseover', (e) =>
            this.props.highlightContestantTable(this.contestant.id)
        ).on('mouseout', (e) =>
            this.props.removeHighlightContestantTable(this.contestant.id)
        )
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
            this.dotText.addTo(this.map)
            this.displayed = true
        }
    }

    hideTrack() {
        if (this.displayed && this.dot) {
            this.lineCollection.removeFrom(this.map)
            this.dot.removeFrom(this.map)
            this.dotText.removeFrom(this.map)
            this.displayed = false
        }
    }

    createPolyline(positions) {
        positions.map((position) => {
            this.lineCollection.addLatLng(position)
        })
    }


    updateBearing() {
        if (this.lineCollection) {
            const positions = this.lineCollection.getLatLngs()
            if (positions.length > 1) {
                const slice = positions.slice(-2)
                this.bearing = getBearing(slice[0].lat, slice[0].lng, slice[1].lat, slice[1].lng)

            }
        }
        this.dot.setIcon(this.createAirplaneIcon())
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
                    this.lineCollection.addLatLng(position)
                })
            }
            this.updateBearing()
        }
    }

    render() {
        return <div/>;
    }

}

const ContestantTrack = connect(mapStateToProps, {
    fetchContestantData,
    initialLoading,
    initialLoadingComplete,
    setDisplay,
    displayOnlyContestantTrack,
    showLowerThirds,
    highlightContestantTable,
    removeHighlightContestantTable
})(ConnectedContestantTrack);
export default ContestantTrack;