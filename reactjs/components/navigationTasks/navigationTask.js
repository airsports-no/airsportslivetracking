import React, {Component} from "react";
import {
    displayAllTracks,
    expandTrackingTable,
    fetchInitialTracks,
    setDisplay,
    shrinkTrackingTable,
    hideLowerThirds, dispatchContestantData, dispatchCurrentTime, dispatchNewContestant, dispatchDeleteContestant
} from "../../actions";
import {connect} from "react-redux";
import ContestantTrack from "../contestantTrack";
import distinctColors from "distinct-colors";
import ContestantRankTable from "../contestantRankTable";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY, TURNING_POINT_DISPLAY} from "../../constants/display-types";
import ContestantDetailsDisplay from "../contestantDetailsDisplay";
import TurningPointDisplay from "../turningPointDisplay";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import PrecisionRenderer from "./precisionRenderer";
import AnrCorridorRenderer from "./anrCorridorRenderer";
import ProhibitedRenderer from "./prohibitedRenderer";
import LandingRenderer from "./landingRenderer";
import ContestRankTable from "../contestRankTable";
import AirsportsRenderer from "./airsportsRenderer";
import {Jawg_Sunny, OpenAIP} from "../leafletLayers";

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
    fetchInitialTracks
}

class ConnectedNavigationTask extends Component {
    constructor(props) {
        super(props);
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
        this.handleMapTurningPointClick = this.handleMapTurningPointClick.bind(this)
        this.rendered = false
        this.client = null;
        this.connectInterval = null;
        this.timeout = 1000
        this.tracklist = []
        this.playbackSecond = -90
        this.waitingInitialLoading = {}
        this.remainingTracks = 999999
        this.renderedTracks = []
        this.colours = distinctColors({count: 25})
    }


    check() {
        if (!this.client || this.client.readyState === WebSocket.CLOSED) this.initiateSession(); //check if websocket instance is closed, if so call `connect` function.
    };

    storePlaybackData(data) {
        data.lastAnnotationLength = 0
        data.lastScoreLength = 0
        data.startTime = new Date(this.props.contestants[data.contestant_id].gate_times[this.props.navigationTask.route.waypoints[0].name])
        this.tracklist.push(data)
    }

    cacheDataWhileLoading(contestantId, data) {
        if (this.waitingInitialLoading[contestantId] !== undefined) {
            this.waitingInitialLoading[contestantId].push(data)
        }
    }

    playBackData() {
        for (const track of this.tracklist) {
            if (track.positions.length > 0) {
                let positions = []
                while (track.positions.length > 0) {
                    const p = track.positions[0]
                    const currentTime = new Date(p.time)
                    if (currentTime.getTime() > track.startTime.getTime() + this.playbackSecond * 1000) {
                        break
                    }
                    positions.push(p)
                    track.positions.shift()
                }
                if (positions.length > 0) {
                    const position = positions[positions.length - 1]
                    const annotations = track.annotations.filter((annotation) => {
                        return (new Date(annotation.time)).getTime() < (new Date(position.time)).getTime()
                    })
                    const scoreLog = track.score_log_entries.filter((log) => {
                        return (new Date(log.time)).getTime() < (new Date(position.time)).getTime()
                    })
                    let score = 0
                    scoreLog.map((log) => {
                        score += log.points
                    })
                    const lastGate = scoreLog.length > 0 ? scoreLog.slice(-1)[0].last_gate : ""
                    const data = {
                        positions: positions,
                        more_data: false,
                        contestant_id: track.contestant_track.contestant,
                        annotations: annotations.length > track.lastAnnotationLength ? annotations : null,
                        latest_time: position.time,
                        progress: position.progress,
                        score_log_entries: scoreLog.length > track.lastScoreLength ? scoreLog : null,
                        contestant_track: {
                            score: score,
                            calculator_finished: false,
                            current_state: scoreLog.length === 0 ? "Waiting..." : "Tracking",
                            last_gate: lastGate,
                            current_leg: lastGate,
                            contestant: track.contestant_track.contestant
                        }
                    }
                    track.lastAnnotationLength = annotations.length
                    track.lastScoreLength = scoreLog.length
                    this.props.dispatchContestantData(data)
                }
            }
        }
        this.playbackSecond += Math.max(1, this.tracklist.length / 3)
        setTimeout(() => this.playBackData(), 300)
    }

    initiateSession() {
        let getUrl = window.location;
        let protocol = "wss"
        if (getUrl.host.includes("localhost")) {
            protocol = "ws"
        }
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/tracks/" + this.props.navigationTaskId + "/")
        this.client.onopen = () => {
            console.log("Client connected")
            clearTimeout(this.connectInterval)
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            if (data.type === "current_time") {
                this.props.dispatchCurrentTime(data.data)
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

            this.timeout = this.timeout + this.timeout; //increment retry interval
            this.connectInterval = setTimeout(() => this.check(), Math.min(10000, this.timeout)); //call check function after timeout
        };
        this.client.onerror = err => {
            console.error(
                "Socket encountered error: ",
                err.message,
                "Closing socket"
            );
            this.client.close();
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
        this.props.setDisplay({displayType: SIMPLE_RANK_DISPLAY})
        this.props.displayAllTracks();
        this.props.hideLowerThirds();
    }


    componentDidMount() {
        if (this.props.displayMap) {
            this.initialiseMap();
        }
        if (this.props.playback) {
            require('./playbackstyle.css')
        }
    }

    getColour(contestantNumber) {
        return this.colours[contestantNumber % this.colours.length]
    }

    componentDidUpdate(previousProps) {
        if (this.props.navigationTask.route !== previousProps.navigationTask.route) {
            if (this.props.displayMap && !this.rendered) {
                this.rendered = true;
                this.remainingTracks = 0
                this.props.navigationTask.contestant_set.map((contestant, index) => {
                    this.remainingTracks++
                    this.waitingInitialLoading[contestant.id] = []
                    this.props.fetchInitialTracks(this.props.contestId, this.props.navigationTaskId, contestant.id)
                })
                this.initiateSession()
            }
        }
        if (this.props.playback) {
            if (this.props.initialTracks !== previousProps.initialTracks) {
                Object.keys(this.props.initialTracks).forEach((key, index) => {
                    if (!this.renderedTracks.includes(key)) {
                        this.renderedTracks.push(key)
                        this.storePlaybackData(this.props.initialTracks[key])
                        this.remainingTracks--
                    }
                })
            }
            if (this.remainingTracks === 0) {
                this.remainingTracks = 9999
                setTimeout(() => this.playBackData(), 1000)
            }
        } else {
            if (this.props.initialTracks !== previousProps.initialTracks) {
                for (const [key, value] of Object.entries(this.props.initialTracks)) {
                    if (!this.renderedTracks.includes(key)) {
                        this.renderedTracks.push(key)
                        console.log(value)
                        this.props.dispatchContestantData(value)
                        if (this.waitingInitialLoading[key] !== undefined) {
                            delete this.waitingInitialLoading[key]
                        }
                    }
                }
            }
        }
        if (this.props.navigationTask.display_background_map !== previousProps.navigationTask.display_background_map || this.props.displayBackgroundMap !== previousProps.displayBackgroundMap) {
            this.fixMapBackground()
        }
        if (this.props.displayOpenAip) {
            OpenAIP.addTo(this.map)
        } else {
            OpenAIP.removeFrom(this.map)
        }

    }

    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
            zoomControl: false,
        }).on('contextmenu', (e) => this.resetToAllContestants(e))
    }

    fixMapBackground() {
        if (this.props.navigationTask.display_background_map && this.props.displayBackgroundMap) {
            Jawg_Sunny.addTo(this.map);
        } else {
            Jawg_Sunny.removeFrom(this.map);
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
                                                       displaySecretGates={this.props.displaySecretGates}/>
                } else if (this.props.navigationTask.scorecard.task_type.includes("airsports") || this.props.navigationTask.scorecard.task_type.includes("poker")) {
                    routeRenderer = <AirsportsRenderer map={this.map} navigationTask={this.props.navigationTask}
                                                       contestants={this.props.contestants}
                                                       currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}
                                                       handleMapTurningPointClick={(turningpoint) => this.handleMapTurningPointClick(turningpoint)}
                                                       displaySecretGates={this.props.displaySecretGates}/>
                } else if (this.props.navigationTask.scorecard.task_type.includes("anr_corridor")) {
                    routeRenderer = <AnrCorridorRenderer map={this.map} navigationTask={this.props.navigationTask}
                                                         contestants={this.props.contestants}
                                                         currentHighlightedContestant={this.props.displayTracks && this.props.displayTracks.length === 1 ? this.props.displayTracks[0] : null}/>
                } else if (this.props.navigationTask.scorecard.task_type.includes("landing")) {
                    routeRenderer = <LandingRenderer map={this.map} navigationTask={this.props.navigationTask}
                                                     contestants={this.props.contestants}/>
                }
                prohibitedRender = <ProhibitedRenderer map={this.map} navigationTask={this.props.navigationTask}
                                                       contestants={this.props.contestants}/>
            }

            let display = <div/>
            if (this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY) {
                if (this.props.displayExpandedTrackingTable) {
                    display = <ContestRankTable contestId={this.props.contestId}
                                                navigationTaskId={this.props.navigationTaskId}
                                                numberOfContestants={Object.keys(this.props.contestants).length}/>
                } else {
                    display = <ContestantRankTable colours={this.colours}
                                                   scoreDecimals={this.props.navigationTask.scorecard.task_type.includes("poker") ? 0 : 0}
                                                   numberOfContestants={Object.keys(this.props.contestants).length}/>
                }
            } else if (this.props.currentDisplay.displayType === CONTESTANT_DETAILS_DISPLAY) {
                display = <ContestantDetailsDisplay contestantId={this.props.currentDisplay.contestantId}
                                                    scoreDecimals={this.props.navigationTask.scorecard.task_type.includes("poker") ? 0 : 0}/>
                this.props.shrinkTrackingTable();
            } else if (this.props.currentDisplay.displayType === TURNING_POINT_DISPLAY) {
                display = <TurningPointDisplay turningPointName={this.props.currentDisplay.turningPoint}
                                               colours={this.colours}/>
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
                                        colour={this.getColour(contestant.contestant_number)}/>
            });
            return <div>
                {routeRenderer}
                {prohibitedRender}
                {mapDisplay}
                {tableDisplay}
            </div>
        }
        return <div/>
    }

}

const NavigationTask = connect(mapStateToProps, mapDispatchToProps)(ConnectedNavigationTask);
export default NavigationTask;