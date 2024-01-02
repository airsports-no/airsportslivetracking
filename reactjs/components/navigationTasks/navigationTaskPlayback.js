import React from "react";
import {
    displayAllTracks,
    expandTrackingTable,
    fetchInitialTracks,
    setDisplay,
    shrinkTrackingTable,
    hideLowerThirds,
    dispatchCurrentTime,
    dispatchNewContestant,
    dispatchDeleteContestant,
    dispatchPlaybackContestantData, dispatchContestantData, dispatchWebSocketConnected,
} from "../../actions";
import {connect} from "react-redux";
import {OpenAIP} from "../leafletLayers";
import {ConnectedNavigationTask} from "./navigationTask";

require('./playbackstyle.css')


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
    dispatchPlaybackContestantData,
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


class ConnectedNavigationTaskPlayback extends ConnectedNavigationTask {
    constructor(props) {
        super(props);
        this.playbackSecond = 0
    }

    storePlaybackData(data) {
        data.lastAnnotationLength = 0
        data.lastScoreLength = 0
        data.startTime = new Date(this.props.contestants[data.contestant_id].gate_times[this.props.navigationTask.route.waypoints[0].name])
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
                        annotations: annotations,
                        latest_time: position.time,
                        progress: position.progress,
                        score_log_entries: scoreLog,
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
        setTimeout(() => this.playBackData(), 200)
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
            }
        }
        if (this.props.initialTracks !== previousProps.initialTracks) {
            for (const [key, value] of Object.entries(this.props.initialTracks)) {
                if (!this.renderedTracks.includes(key)) {
                    this.renderedTracks.push(key)
                    this.storePlaybackData(this.props.initialTracks[key])
                    this.props.dispatchPlaybackContestantData(value)
                    this.remainingTracks--
                }
            }
        }

        if (this.remainingTracks === 0) {
            this.remainingTracks = 9999
            setTimeout(() => this.playBackData(), 1000)
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
}

const NavigationTaskPlayback = connect(mapStateToProps, mapDispatchToProps)(ConnectedNavigationTaskPlayback);
export default NavigationTaskPlayback;