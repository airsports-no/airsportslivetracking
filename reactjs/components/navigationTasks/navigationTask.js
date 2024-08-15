
import React, { Component } from "react";
import {
    displayAllTracks,
    expandTrackingTable,
    setDisplay,
    shrinkTrackingTable,
    hideLowerThirds,
    dispatchContestantData,
    dispatchCurrentTime,
    dispatchNewContestant,
    dispatchDeleteContestant,
    dispatchWebSocketConnected
} from "../../actions";
import { connect } from "react-redux";
import ContestantTrack from "./contestantTrack";
import distinctColors from "distinct-colors";
import ContestantRankTable from "./contestantRankTable";
import { CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY } from "../../constants/display-types";
import ContestantDetailsDisplay from "./contestantDetailsDisplay";
import { w3cwebsocket as W3CWebSocket } from "websocket";
import PrecisionRenderer from "./trackRenderers/precisionRenderer";
import AnrCorridorRenderer from "./trackRenderers/anrCorridorRenderer";
import ProhibitedRenderer from "./trackRenderers/prohibitedRenderer";
import LandingRenderer from "./trackRenderers/landingRenderer";
import FreeWaypointRenderer from "./trackRenderers/freeWaypointRenderer";
import ContestRankTable from "../resultsService/contestRankTable";
import AirsportsRenderer from "./trackRenderers/airsportsRenderer";
import { Jawg_Sunny, OpenAIP } from "../leafletLayers";

export const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    contestants: state.contestants,
    currentDisplay: state.currentDisplay,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
    displayOpenAip: state.displayOpenAip,
    displayTracks: state.displayTracks,
    displaySecretGates: state.displaySecretGates,
    displayBackgroundMap: state.displayBackgroundMap,
    initialLoading: state.initialLoadingContestantData,

})
export const mapDispatchToProps = {
    dispatchContestantData,
    dispatchCurrentTime,
    dispatchNewContestant,
    dispatchDeleteContestant,
    setDisplay,
    displayAllTracks,
    expandTrackingTable,
    shrinkTrackingTable,
    hideLowerThirds,
    dispatchWebSocketConnected
}


export class ConnectedNavigationTask extends Component {
    constructor(props) {
        super(props);
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
        this.rendered = false
        this.client = null;
        this.offline = true
        this.connectInterval = null;
        this.timeout = 1000
        this.tracklist = []
        this.waitingInitialLoading = {}
        this.remainingTracks = 999999
        this.renderedTracks = []
        this.lastTimeReceived = null
        this.checkReceivedTimeInterval = null
        this.colours = distinctColors({ count: 25 })
        this.sunny = Jawg_Sunny()
        this.openaip = OpenAIP()
    }


    checkReceivedTime() {
        if (this.lastTimeReceived) {
            this.offline = new Date().getTime() - this.lastTimeReceived > 20 * 1000;
            this.props.dispatchWebSocketConnected(!this.offline)
        }
    }


    check() {
        if (!this.client || this.client.readyState === WebSocket.CLOSED) this.initiateSession(); //check if websocket instance is closed, if so call `connect` function.
    };

    cacheDataWhileLoading(contestantId, data) {
        if (!(contestantId in this.waitingInitialLoading[contestantId])) {
            this.waitingInitialLoading[contestantId] = []
        }
        this.waitingInitialLoading[contestantId].push(data)

    }

    initiateSession() {
        clearInterval(this.checkReceivedTimeInterval)
        let getUrl = window.location;
        let protocol = "wss"
        if (getUrl.host.includes("localhost")) {
            protocol = "ws"
        }
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/tracks/" + this.props.navigationTaskId + "/")
        this.client.onopen = () => {
            this.offline = false
            this.props.dispatchWebSocketConnected(true)
            this.checkReceivedTimeInterval = setInterval(() => this.checkReceivedTime(), 5000)
            console.log("Client connected")
            clearTimeout(this.connectInterval)
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            if (data.type === "current_time") {
                this.props.dispatchCurrentTime(data.data)
                this.lastTimeReceived = new Date()
            } else if (data.type === "contestant" && this.props.contestantIds.length === 0) {
                this.props.dispatchNewContestant(JSON.parse(data.data))
            } else if (data.type === "contestant_delete") {
                this.props.dispatchDeleteContestant(JSON.parse(data.data))
            } else {
                const trackData = JSON.parse(data.data)
                if (this.props.initialLoading[trackData.contestant_id]) {
                    this.cacheDataWhileLoading(trackData.contestant_id, trackData)
                } else {
                    if (trackData.contestant_id in this.waitingInitialLoading[trackData.contestant_id]) {
                        for (let p of this.waitingInitialLoading[trackData.contestant_id]) {
                            this.props.dispatchContestantData(p)
                        }
                        delete this.waitingInitialLoading[trackData.contestant_id]
                    }
                    this.props.dispatchContestantData(trackData)
                }
            }
        };
        this.client.onclose = (e) => {
            console.log(
                `Socket is closed. Reconnect will be attempted in ${Math.min(
                    10000 / 1000,
                    (this.timeout + this.timeout) / 1000
                )} second.`,
                e.reason
            );
            this.offline = true
            this.props.dispatchWebSocketConnected(false)

            this.timeout = this.timeout + this.timeout; //increment retry interval
            this.connectInterval = setTimeout(() => this.check(), Math.min(10000, this.timeout)); //call check function after timeout
        };
        this.client.onerror = err => {
            console.error(
                "Socket encountered error: ",
                err.message,
                "Closing socket"
            );
            this.offline = true
            this.client.close();
            this.props.dispatchWebSocketConnected(false)
        };
    }



    resetToAllContestants(e) {
        L.DomEvent.stopPropagation(e)
        this.props.setDisplay({ displayType: SIMPLE_RANK_DISPLAY })
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }


    componentDidMount() {
        if (this.props.displayMap) {
            this.initialiseMap();
        }
    }

    getColour(contestantNumber) {
        return this.colours[contestantNumber % this.colours.length]
    }

    componentDidUpdate(previousProps) {
        if (this.props.navigationTask.route !== previousProps.navigationTask.route) {
            if (this.props.displayMap && !this.rendered) {
                this.rendered = true;
                this.remainingTracks = this.props.navigationTask.contestant_set.length
                this.props.navigationTask.contestant_set.map((contestant, index) => {
                    this.waitingInitialLoading[contestant.id] = {}
                })
                this.initiateSession()
            }
        }
        if (this.props.navigationTask.display_background_map !== previousProps.navigationTask.display_background_map || this.props.displayBackgroundMap !== previousProps.displayBackgroundMap) {
            this.fixMapBackground()
        }
        if (this.props.displayOpenAip) {
            this.openaip.addTo(this.map)
        } else {
            this.openaip.removeFrom(this.map)
        }

    }

    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
            zoomControl: false,
            maxZoom: 14,  // Required when there is no background map, otherwise it may crash
        }).on('contextmenu', (e) => this.resetToAllContestants(e))
    }

    fixMapBackground() {
        if (this.props.navigationTask.display_background_map && this.props.displayBackgroundMap) {
            this.sunny.addTo(this.map);
        } else {
            this.sunny.removeFrom(this.map);
        }
    }


    render() {
        if (this.props.navigationTask.contestant_set !== undefined) {
            let routeRenderer = null;
            let prohibitedRender = null;
            let freeWaypointRenderer = null
            if (this.props.navigationTask.scorecard !== undefined) {
                if (this.props.navigationTask.scorecard.task_type.includes("precision") || this.props.navigationTask.scorecard.task_type.includes("cima_precision") || this.props.navigationTask.scorecard.task_type.includes("poker")) {
                    routeRenderer = <PrecisionRenderer map={this.map} navigationTask={this.props.navigationTask}
                        contestants={this.props.contestants}
                        currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}
                        displaySecretGates={this.props.displaySecretGates} />
                    freeWaypointRenderer = <FreeWaypointRenderer navigationTask={this.props.navigationTask}
                        contestants={this.props.contestants} map={this.map}
                        currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}
                    />
                } else if (this.props.navigationTask.scorecard.task_type.includes("airsports") || this.props.navigationTask.scorecard.task_type.includes("airsportchallenge") || this.props.navigationTask.scorecard.task_type.includes("poker")) {
                    routeRenderer = <AirsportsRenderer map={this.map} navigationTask={this.props.navigationTask} key={this.props.navigationTask}
                        contestants={this.props.contestants}
                        currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}
                        displaySecretGates={this.props.displaySecretGates} />
                } else if (this.props.navigationTask.scorecard.task_type.includes("anr_corridor")) {
                    routeRenderer = <AnrCorridorRenderer map={this.map} navigationTask={this.props.navigationTask}
                        contestants={this.props.contestants}
                        currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null} />
                } else if (this.props.navigationTask.scorecard.task_type.includes("landing")) {
                    routeRenderer = <LandingRenderer map={this.map} navigationTask={this.props.navigationTask}
                        contestants={this.props.contestants} />
                }
                prohibitedRender = <ProhibitedRenderer map={this.map} navigationTask={this.props.navigationTask}
                    contestants={this.props.contestants} />
            }

            let display = <div />
            if (this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY) {
                if (this.props.displayExpandedTrackingTable) {
                    display = <ContestRankTable contestId={this.props.contestId}
                        navigationTaskId={this.props.navigationTaskId}
                        numberOfContestants={Object.keys(this.props.contestants).length} />
                } else {
                    display = <ContestantRankTable colours={this.colours}
                        scoreDecimals={this.props.navigationTask.scorecard.task_type.includes("poker") ? 0 : 0}
                        numberOfContestants={Object.keys(this.props.contestants).length} />
                }
            } else if (this.props.currentDisplay.displayType === CONTESTANT_DETAILS_DISPLAY) {
                display = <ContestantDetailsDisplay contestantId={this.props.currentDisplay.contestantId}
                    scoreDecimals={this.props.navigationTask.scorecard.task_type.includes("poker") ? 0 : 0} />
                this.props.shrinkTrackingTable();
            }
            const tableDisplay = <div>
                {display}
            </div>
            const mapDisplay = Object.entries(this.props.contestants).map(([key, contestant], index) => {
                return <ContestantTrack map={this.map} key={contestant.id}
                    contestant={contestant} contestId={this.props.contestId}
                    navigationTask={this.props.navigationTask}
                    displayMap={this.props.displayMap}
                    colour={this.getColour(contestant.contestant_number)} />
            });
            return <div>
                {routeRenderer}
                {prohibitedRender}
                {freeWaypointRenderer}
                {mapDisplay}
                {tableDisplay}
            </div>
        }
        return <div />
    }

}

const NavigationTask = connect(mapStateToProps, mapDispatchToProps)(ConnectedNavigationTask);
export default NavigationTask;