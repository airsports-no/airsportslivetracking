import React, {Component} from "react";
import {connect} from "react-redux";
import {
    displayOnlyContestantTrack,
    fetchContestantData,
    initialLoading,
    initialLoadingComplete,
    setDisplay, showLowerThirds
} from "../actions";
import 'leaflet'
import 'leaflet.markercluster'
import {anomalyAnnotationIcon, informationAnnotationIcon} from "./iconDefinitions";
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"
import {contestantLongForm, contestantShortForm} from "../utilities";
import {CONTESTANT_DETAILS_DISPLAY} from "../constants/display-types";

const L = window['L']

const mapStateToProps = (state, props) => ({
    contestantData: state.contestantData[props.contestant.id],
    displayTracks: state.displayTracks,
    isFetching: state.isFetchingContestantData[props.contestant.id],
    initialLoading: state.initialLoadingContestantData[props.contestant.id]
})

class ConnectedContestantTrack extends Component {
    constructor(props) {
        super(props);
        this.map = props.map
        this.colour = props.colour
        this.contestant = props.contestant
        this.markers = L.markerClusterGroup()
        this.lineCollection = null;
        this.dot = null;
        this.previousLastTime = null;
        this.lastNewData = null;
        this.annotationLayer = L.layerGroup()
        const size = 24;
        this.airplaneIcon = L.divIcon({
            html: '<i class="fa fa-plane" style="color: ' + this.colour + '"><br/>' + contestantShortForm(props.contestant) + '</i>',
            iconSize: [size, size],
            iconAnchor: [size, size / 2],
            className: "myAirplaneIcon"
        })
        this.iconMap = {
            anomaly: anomalyAnnotationIcon, information: informationAnnotationIcon
        }
        this.props.initialLoading(this.contestant.id)
        // this.fetchNextData(false)
        this.handleContestantLinkClick = this.handleContestantLinkClick.bind(this)
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

    createLiveEntities(positions) {
        const newest_position = positions.slice(-1)[0];

        this.lineCollection = L.polyline(positions, {
            color: this.colour
        }).on('click', (e) => this.handleContestantLinkClick(e, this.contestant.id))
        this.dot = L.marker(newest_position, {icon: this.airplaneIcon}).bindTooltip(contestantLongForm(this.contestant), {
            permanent: false
        }).on('click', (e) => this.handleContestantLinkClick(e, this.contestant.id))
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
                const s = b.slice(-1)[0]
                if (s) {
                    this.dot.setLatLng(b.slice(-1)[0])
                }
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

const ContestantTrack = connect(mapStateToProps, {
    fetchContestantData,
    initialLoading,
    initialLoadingComplete,
    setDisplay,
    displayOnlyContestantTrack,
    showLowerThirds
})(ConnectedContestantTrack);
export default ContestantTrack;