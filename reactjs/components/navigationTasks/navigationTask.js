import React, { Component } from "react";
import {
    displayAllTracks,
    expandTrackingTable,
    fetchInitialTracks,
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
import { CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY, TURNING_POINT_DISPLAY } from "../../constants/display-types";
import ContestantDetailsDisplay from "./contestantDetailsDisplay";
import TurningPointDisplay from "./turningPointDisplay";
import { w3cwebsocket as W3CWebSocket } from "websocket";
import PrecisionRenderer from "./trackRenderers/precisionRenderer";
import AnrCorridorRenderer from "./trackRenderers/anrCorridorRenderer";
import ProhibitedRenderer from "./trackRenderers/prohibitedRenderer";
import LandingRenderer from "./trackRenderers/landingRenderer";
import ContestRankTable from "../resultsService/contestRankTable";
import AirsportsRenderer from "./trackRenderers/airsportsRenderer";
import { Jawg_Sunny, OpenAIP } from "../leafletLayers";

export const mapStateToProps = (state, props) => ({
    initialTracks: state.initialTracks,
    navigationTask: state.navigationTask,
    contestants: state.contestants,
    currentDisplay: state.currentDisplay,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
    displayOpenAip: state.displayOpenAip,
    displayTracks: state.displayTracks,
    displaySecretGates: state.displaySecretGates,
    displayBackgroundMap: state.displayBackgroundMap
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
    fetchInitialTracks,
    dispatchWebSocketConnected
}

const PARALLEL_FETCHING_INITIAL_TRACKS = false

export class ConnectedNavigationTask extends Component {
    constructor(props) {
        super(props);
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
        this.handleMapTurningPointClick = this.handleMapTurningPointClick.bind(this)
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
        if (this.waitingInitialLoading[contestantId] !== undefined) {
            this.waitingInitialLoading[contestantId].push(data)
        }
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
                // Do not add new contestants if we are filtering contestant IDs
                this.props.dispatchNewContestant(JSON.parse(data.data))
            } else if (data.type === "contestant_delete") {
                this.props.dispatchDeleteContestant(JSON.parse(data.data))
            } else {
                const trackData = JSON.parse(data.data)
                if (this.waitingInitialLoading[trackData.contestant_id] !== undefined) {
                    this.cacheDataWhileLoading(trackData.contestant_id, trackData)
                } else {
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

    handleMapTurningPointClick(turningPoint) {
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
        this.props.setDisplay({
            displayType: TURNING_POINT_DISPLAY,
            turningPoint: turningPoint
        })
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
                if (!PARALLEL_FETCHING_INITIAL_TRACKS) {
                    if (this.remainingTracks > 0) {
                        this.props.fetchInitialTracks(this.props.contestId, this.props.navigationTaskId, this.props.navigationTask.contestant_set[0].id)
                        this.waitingInitialLoading[this.props.navigationTask.contestant_set[0].id] = []
                    }
                } else {

                    this.props.navigationTask.contestant_set.map((contestant, index) => {
                        this.waitingInitialLoading[contestant.id] = []
                        this.props.fetchInitialTracks(this.props.contestId, this.props.navigationTaskId, contestant.id)
                    })
                }
                this.initiateSession()
            }
        }
        if (this.props.initialTracks !== previousProps.initialTracks) {
            for (const [key, value] of Object.entries(this.props.initialTracks)) {
                if (!this.renderedTracks.includes(key)) {
                    this.renderedTracks.push(key)
                    console.log(value)
                    this.props.dispatchContestantData(value)
                    if (this.waitingInitialLoading[key] !== undefined) {
                        // for(let p of this.waitingInitialLoading[key]){
                        //     this.props.dispatchContestantData(p)
                        // }
                        delete this.waitingInitialLoading[key]
                    }
                }
            }
            if (!PARALLEL_FETCHING_INITIAL_TRACKS) {
                for (const contestant of this.props.navigationTask.contestant_set) {
                    if (!this.renderedTracks.includes(contestant.id.toString())) {
                        this.props.fetchInitialTracks(this.props.contestId, this.props.navigationTaskId, contestant.id)
                        this.waitingInitialLoading[contestant.id] = []
                        break
                    }
                }
            }
        }
        if (this.remainingTracks === 0) {
            this.remainingTracks = 9999
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
            if (this.props.navigationTask.scorecard !== undefined) {
                if (this.props.navigationTask.scorecard.task_type.includes("precision") || this.props.navigationTask.scorecard.task_type.includes("poker")) {
                    routeRenderer = <PrecisionRenderer map={this.map} navigationTask={this.props.navigationTask}
                        contestants={this.props.contestants}
                        currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}
                        handleMapTurningPointClick={(turningpoint) => this.handleMapTurningPointClick(turningpoint)}
                        displaySecretGates={this.props.displaySecretGates} />
                } else if (this.props.navigationTask.scorecard.task_type.includes("airsports") || this.props.navigationTask.scorecard.task_type.includes("airsportchallenge") || this.props.navigationTask.scorecard.task_type.includes("poker")) {
                    routeRenderer = <AirsportsRenderer map={this.map} navigationTask={this.props.navigationTask}
                        contestants={this.props.contestants}
                        currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}
                        handleMapTurningPointClick={(turningpoint) => this.handleMapTurningPointClick(turningpoint)}
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
            } else if (this.props.currentDisplay.displayType === TURNING_POINT_DISPLAY) {
                display = <TurningPointDisplay turningPointName={this.props.currentDisplay.turningPoint}
                    colours={this.colours} />
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
                {mapDisplay}
                {tableDisplay}
            </div>
        }
        return <div />
    }

}

const NavigationTask = connect(mapStateToProps, mapDispatchToProps)(ConnectedNavigationTask);
export default NavigationTask;