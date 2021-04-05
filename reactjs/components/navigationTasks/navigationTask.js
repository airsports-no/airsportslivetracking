import React, {Component} from "react";
import {
    displayAllTracks,
    expandTrackingTable,
    fetchNavigationTask,
    setDisplay,
    shrinkTrackingTable,
    hideLowerThirds, dispatchContestantData
} from "../../actions";
import {connect} from "react-redux";
import {circle, divIcon, marker, polyline, tileLayer} from "leaflet";
import ContestantTrack from "../contestantTrack";
import distinctColors from "distinct-colors";
import {compareContestantNumber} from "../../utilities";
import ContestantRankTable from "../contestantRankTable";
import {CONTESTANT_DETAILS_DISPLAY, SIMPLE_RANK_DISPLAY, TURNING_POINT_DISPLAY} from "../../constants/display-types";
import ContestantDetailsDisplay from "../contestantDetailsDisplay";
import TurningPointDisplay from "../turningPointDisplay";
import {w3cwebsocket as W3CWebSocket} from "websocket";
import PrecisionRenderer from "./precisionRenderer";
import AnrCorridorRenderer from "./anrCorridorRenderer";
import ProhibitedRenderer from "./prohibitedRenderer";
import LandingRenderer from "./landingRenderer";

const L = window['L']


export const mapStateToProps = (state, props) => ({
    navigationTask: state.navigationTask,
    currentDisplay: state.currentDisplay,
    displayExpandedTrackingTable: state.displayExpandedTrackingTable,
})
export const mapDispatchToProps = {
    dispatchContestantData,
    setDisplay,
    displayAllTracks,
    expandTrackingTable,
    shrinkTrackingTable,
    hideLowerThirds
}

class ConnectedNavigationTask extends Component {
    constructor(props) {
        super(props);
        this.resetToAllContestants = this.resetToAllContestants.bind(this)
        this.handleMapTurningPointClick = this.handleMapTurningPointClick.bind(this)
        this.rendered = false
        this.client = null;
        this.connectInterval = null;
        this.weTimeOut = 1000
        this.tracklist = []
        this.playbackSecond = -90
    }


    check() {
        if (!this.client || this.client.readyState === WebSocket.CLOSED) this.initiateSession(); //check if websocket instance is closed, if so call `connect` function.
    };

    storePlaybackData(data) {
        data.logLength = 0
        data.startTime = new Date(this.props.navigationTask.contestant_set.find((contestant) => {
            return contestant.id === data.contestant_id
        }).gate_times[this.props.navigationTask.route.waypoints[0].name])
        this.tracklist.push(data)
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
                    let annotations = []
                    while (track.annotations.length > 0) {
                        if ((new Date(track.annotations[0].time)).getTime() < (new Date(position.time)).getTime()) {
                            annotations.push(track.annotations.shift())
                        } else {
                            break
                        }
                    }
                    // let scoreLog = track.contestant_track.score_log.filter((log) => {
                    //     return new Date(log.time) < new Date(position.time)
                    // })
                    track.logLength += annotations.length
                    const scoreLog = track.contestant_track.score_log.slice(0, track.logLength)
                    let score = 0
                    scoreLog.map((log) => {
                        score += log.points
                    })
                    const lastGate = scoreLog.length > 0 ? scoreLog.slice(-1)[0].last_gate : ""
                    const data = {
                        positions: positions,
                        more_data: false,
                        contestant_id: track.contestant_track.contestant,
                        annotations: annotations,
                        latest_time: position.time,
                        progress: position.progress,
                        contestant_track: {
                            score_log: scoreLog,
                            score: score,
                            calculator_finished: false,
                            score_per_gate: {},
                            current_state: track.logLength === 0 ? "Waiting..." : "Tracking",
                            last_gate: lastGate,
                            current_leg: lastGate,
                            contestant: track.contestant_track.contestant
                        }
                    }
                    this.props.dispatchContestantData(data)
                }
            }
        }
        this.playbackSecond += this.tracklist.length / 2
        setTimeout(() => this.playBackData(), 200)
    }

    initiateSession() {
        let getUrl = window.location;
        let protocol = "wss"
        if (getUrl.host.includes("localhost")) {
            protocol = "ws"
        }
        if (this.props.playback) {
            setTimeout(() => this.playBackData(), 1000)
        }
        this.client = new W3CWebSocket(protocol + "://" + getUrl.host + "/ws/tracks/" + this.props.navigationTaskId + "/")
        this.client.onopen = () => {
            console.log("Client connected")
            clearTimeout(this.connectInterval)
        };
        this.client.onmessage = (message) => {
            let data = JSON.parse(message.data);
            if (this.props.playback) {
                this.storePlaybackData(data)
            } else {
                this.props.dispatchContestantData(data)
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
            this.connectInterval = setTimeout(() => this.check(), Math.min(10000, this.wsTimeOut)); //call check function after timeout
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
    }


    buildColourMap() {
        const colours = distinctColors({count: this.props.navigationTask.contestant_set.length})
        this.props.navigationTask.contestant_set.sort(compareContestantNumber)
        let colourMap = {}
        this.props.navigationTask.contestant_set.map((contestant, index) => {
            colourMap[contestant.contestant_number] = colours[index]
        })
        return colourMap
    }


    componentDidUpdate(previousProps) {
        if (this.props.navigationTask.route !== previousProps.navigationTask.route) {
            if (this.props.displayMap && !this.rendered) {
                this.rendered = true;
                this.initiateSession()

            }
        }
        if (this.props.navigationTask.display_background_map !== previousProps.navigationTask.display_background_map) {
            this.fixMapBackground()
        }

    }

    initialiseMap() {
        this.map = L.map('cesiumContainer', {
            zoomDelta: 0.25,
            zoomSnap: 0.25,
        }).on('contextmenu', (e) => this.resetToAllContestants(e))
        // const logoContainer = document.getElementById("logoContainer")
        // const mapControlContainer = document.getElementsByClassName("leaflet-control")[0]
        // mapControlContainer.appendChild(logoContainer)
    }

    fixMapBackground() {
        const token = "pk.eyJ1Ijoia29sYWYiLCJhIjoiY2tmNm0zYW55MHJrMDJ0cnZvZ2h6MTJhOSJ9.3IOApjwnK81p6_a0GsDL-A"
        if (this.props.navigationTask.display_background_map) {
            tileLayer('https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}', {
                attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, <a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
                maxZoom: 18,
                id: 'mapbox/streets-v11',
                tileSize: 512,
                zoomOffset: -1,
                accessToken: token
            }).addTo(this.map);
        }
    }


    render() {
        if (this.props.navigationTask.contestant_set !== undefined) {
            let routeRenderer = null;
            let prohibitedRender = null;
            if (this.props.navigationTask.scorecard !== undefined) {
                if (this.props.navigationTask.scorecard_data.task_type.includes("precision") || this.props.navigationTask.scorecard_data.task_type.includes("poker")) {
                    routeRenderer = <PrecisionRenderer map={this.map} navigationTask={this.props.navigationTask}/>
                } else if (this.props.navigationTask.scorecard_data.task_type.includes("anr_corridor")) {
                    routeRenderer = <AnrCorridorRenderer map={this.map} navigationTask={this.props.navigationTask}/>
                } else if (this.props.navigationTask.scorecard_data.task_type.includes("landing")) {
                    routeRenderer = <LandingRenderer map={this.map} navigationTask={this.props.navigationTask}/>
                }
                prohibitedRender = <ProhibitedRenderer map={this.map} navigationTask={this.props.navigationTask}/>
            }

            const colourMap = this.buildColourMap()
            let display = <div/>
            if (this.props.currentDisplay.displayType === SIMPLE_RANK_DISPLAY) {
                display = <ContestantRankTable colourMap={colourMap}
                                               numberOfContestants={this.props.navigationTask.contestant_set.length}/>
            } else if (this.props.currentDisplay.displayType === CONTESTANT_DETAILS_DISPLAY) {
                display = <ContestantDetailsDisplay contestantId={this.props.currentDisplay.contestantId}/>
                this.props.shrinkTrackingTable();
            } else if (this.props.currentDisplay.displayType === TURNING_POINT_DISPLAY) {
                display = <TurningPointDisplay turningPointName={this.props.currentDisplay.turningPoint}
                                               colourMap={colourMap}/>
                this.props.shrinkTrackingTable();
            }
            const tableDisplay = <div>
                {/*<div className={"card-body"}>*/}
                {/*<div className={"card–text"}>*/}
                {/*<div className={"card-title"}>*/}
                {/*</div>*/}
                {display}
                {/*</div>*/}
                {/*</div>*/}
            </div>
            const mapDisplay = this.props.navigationTask.contestant_set.map((contestant, index) => {
                return <ContestantTrack map={this.map} key={contestant.id} fetchInterval={10000}
                                        contestant={contestant} contestId={this.props.contestId}
                                        navigationTaskId={this.props.navigationTaskId}
                                        displayMap={this.props.displayMap}
                                        colour={colourMap[contestant.contestant_number]}/>
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