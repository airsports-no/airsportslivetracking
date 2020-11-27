import React from "react";
import {ContestantTracks} from "./ContestantTrack";
import axios from "axios";
import {circle, divIcon, marker, polyline} from "leaflet"

// import EllipsisWithTooltip from 'react-ellipsis-with-tooltip'
import LinesEllipsis from 'react-lines-ellipsis'
import responsiveHOC from 'react-lines-ellipsis/lib/responsiveHOC'

var moment = require("moment");

const ResponsiveEllipsis = responsiveHOC()(LinesEllipsis)
import "bootstrap/dist/css/bootstrap.min.css"
import Table from "react-bootstrap/Table";

const DisplayTypes = {
    scoreboard: 0,
    trackDetails: 1,
    turningpointstanding: 2,
    simpleScoreboard: 3
}

const ScoreTypes = {
    absoluteScore: 0,
    relativeScorePercent: 1
}


const ScoreTypeName = {
    0: "Absolute score",
    1: "Score percentage"
}
const scoreTypeList = [ScoreTypes.absoluteScore, ScoreTypes.relativeScorePercent]


function getScore(scoreType, minScore, score) {
    if (scoreType === ScoreTypes.absoluteScore) {
        return score
    } else if (scoreType === ScoreTypes.relativeScorePercent) {
        return ((100 * score / minScore) - 100).toFixed(1) + "%"
    }
}

function getMinimumScoreAboveZero(contestants) {
    return contestants.filter((p) => {
        return p.score !== 0
    }).reduce((min, p) => p.score < min ? p.score : min, 999999999);
}

// class FullTableRow extends React.Component{
//
// }

export class Tracker extends React.Component {
    constructor(props) {
        super(props)
        this.contest = props.contest;
        this.startTime = new Date(this.contest.start_time)
        this.finishTime = new Date(this.contest.finish_time)
        this.lastDataTime = {}
        this.liveMode = props.liveMode
        this.map = props.map;
        this.renderMap = props.displayMap
        this.tracks = new ContestantTracks(this.map, this.startTime, this.finishTime, this.contest.contestant_set, this.contest.track, (contestant) => this.updateScoreCallback(contestant));
        this.state = {
            score: {},
            currentTime: new Date().toLocaleString(),
            currentDisplay: DisplayTypes.simpleScoreboard,
            scoreType: ScoreTypes.absoluteScore
        }
        this.turningPointsDisplay = this.contest.track.waypoints.map((waypoint) => {
            return <li><a href={"#"} onClick={() => {
                this.setState({currentDisplay: DisplayTypes.turningpointstanding, turningPoint: waypoint.name})
            }} key={"tplist" + waypoint.name}>{waypoint.name}</a></li>
        })
        if (this.renderMap) {
            this.renderTrack();
        }
        this.fetchNextData();
    }

    getTrackingStateBackgroundClass(state) {
        if (["Tracking", "Procedure turn"].includes(state)) return "greenBackground";
        if (["Backtracking", "Failed procedure turn"].includes(state)) return "redBackground"
        return ""
    }

    fetchNextData() {
        for (const contestant of this.tracks.contestants.contestants) {
            let tail = ""
            if (this.lastDataTime.hasOwnProperty(contestant.id))
                tail = "?from_time=" + this.lastDataTime[contestant.id].toISOString()
            axios.get("/display/api/contestant/track_data/" + contestant.id + tail).then((result) => {
                console.log(result.data)
                if (result.data.latest_time)
                    this.lastDataTime[contestant.id] = new Date(result.data.latest_time)
                this.tracks.addData(result.data.positions, result.data.annotations, result.data.contestant_tracks)
            }).catch(error => {
                if (error.response) {
                    console.log("Response data error: " + error)
                } else if (error.request) {
                    console.log("Request data error: " + error)
                } else {
                    throw error
                }
            })
        }
        setTimeout(() => this.fetchNextData(), this.props.fetchInterval)
    }

    updateScoreCallback(contestant) {
        let existing = this.state.score;
        existing[contestant.contestantNumber] = contestant;
        this.setState({score: existing})
    }


    renderTrack() {
        for (const key in this.contest.track.waypoints) {
            if (this.contest.track.waypoints.hasOwnProperty(key)) {
                let gate = this.contest.track.waypoints[key];
                polyline([[gate.gate_line[1], gate.gate_line[0]], [gate.gate_line[3], gate.gate_line[2]]], {
                    color: "blue"
                }).addTo(this.map)
            }
        }
        let turningPoints = this.contest.track.waypoints.filter((waypoint) => {
            return waypoint.type === "tp"
        }).map((waypoint) => {
            return [waypoint.latitude, waypoint.longitude]
        });
        this.contest.track.waypoints.map((waypoint) => {
            marker([waypoint.latitude, waypoint.longitude], {
                color: "blue",
                icon: divIcon({
                    html: '<i class="fas"><br/>' + waypoint.name + '</i>',
                    iconSize: [20, 20],
                    className: "myGateIcon"
                })
            }).bindTooltip(waypoint.name, {permanent: false}).addTo(this.map)
        });
        this.contest.track.waypoints.filter((waypoint) => {
            return waypoint.is_procedure_turn
        }).map((waypoint) => {
            circle([waypoint.latitude, waypoint.longitude], {
                radius: 500,
                color: "blue"
            }).addTo(this.map)
        })
        // Temporarily plot range circles
        // this.contest.track.waypoints.map((waypoint) => {
        //     circle([waypoint.latitude, waypoint.longitude], {
        //         radius: waypoint.insideDistance,
        //         color: "orange"
        //     }).addTo(this.map)
        // })
        // Plot starting line
        // const gate = this.contest.track.starting_line
        // polyline([[gate.gate_line[1], gate.gate_line[0]], [gate.gate_line[3], gate.gate_line[2]]], {
        //             color: "red"
        //         }).addTo(this.map)
        let route = polyline(turningPoints, {
            color: "blue"
        }).addTo(this.map)
        this.map.fitBounds(route.getBounds(), {padding: [50, 50]})

    }

    compareScore(a, b) {
        if (a.score > b.score) return 1;
        if (a.score < b.score) return -1;
        return 0
    }


    displayScoreboard() {
        if (this.tracks) {
            this.tracks.showAllTracks()
            this.tracks.hideAllAnnotations()
        }
        let contestants = []
        for (const key in this.state.score) {
            if (this.state.score.hasOwnProperty(key)) {
                contestants.push(this.state.score[key])
            }
        }
        contestants.sort(this.compareScore)
        contestants = contestants.filter((contestant) => {
            return contestant.trackState !== "Waiting..."
        })
        const minimumScore = getMinimumScoreAboveZero(contestants)
        console.log("Minimum score: " + minimumScore)
        let position = 1
        const listItems = contestants.map((d) => <tr
            key={"leaderboard" + d.contestantNumber}>
            <td style={{"backgroundColor": d.colour}}>&nbsp;</td>
            <td>{position++}</td>
            <td><a href={"#"}
                   onClick={() => this.setState({
                       currentDisplay: DisplayTypes.trackDetails,
                       displayTrack: this.tracks.getTrackForContestant(d.id)
                   })}>{d.contestantNumber} {d.displayString()}</a></td>
            <td>{getScore(this.state.scoreType, minimumScore, d.score)}</td>
            <td className={this.getTrackingStateBackgroundClass(d.trackState)}>{d.trackState}</td>
            <td><ResponsiveEllipsis text={d.latestStatus} maxLine={1}/></td>
            {/*<td><EllipsisWithTooltip placement="bottom">{d.latestStatus}</EllipsisWithTooltip></td>*/}
            <td>{d.currentLeg}</td>
        </tr>);
        return <Table bordered hover striped size={"sm"} responsive>
            <thead>
            <tr>
                <td/>
                <td>#</td>
                <td>Team</td>
                <td>Score</td>
                <td>State</td>
                <td>Latest event</td>
                <td>Leg</td>
            </tr>
            </thead>
            <tbody>{listItems}</tbody>
        </Table>
    }

    displaySimpleScoreBoard() {
        if (this.tracks) {
            this.tracks.showAllTracks()
            this.tracks.hideAllAnnotations()
        }
        let contestants = []
        for (const key in this.state.score) {
            if (this.state.score.hasOwnProperty(key)) {
                contestants.push(this.state.score[key])
            }
        }
        contestants.sort(this.compareScore)
        contestants = contestants.filter((contestant) => {
            return contestant.trackState !== "Waiting..."
        })
        const minimumScore = getMinimumScoreAboveZero(contestants)
        let position = 1
        const listItems = contestants.map((d) => <tr
            key={"leaderboard" + d.contestantNumber}>
            <td style={{"backgroundColor": d.colour}}>&nbsp;</td>
            <td>{position++}</td>
            <td><a href={"#"}
                   onClick={() => this.setState({
                       currentDisplay: DisplayTypes.trackDetails,
                       displayTrack: this.tracks.getTrackForContestant(d.id)
                   })}>{d.contestantNumber} {d.displayString()}</a></td>
            <td>{getScore(this.state.scoreType, minimumScore, d.score)}</td>
            <td className={this.getTrackingStateBackgroundClass(d.trackState)}>{d.trackState}</td>
            <td>{d.lastGate}</td>
            {/*<td>{moment.duration(d.lastGateTimeDifference, "seconds").format()}</td>*/}
            <td>{d.lastGateTimeDifference}</td>
        </tr>);
        return <Table bordered hover striped size={"sm"} responsive>
            <thead>
            <tr>
                <td/>
                <td>#</td>
                <td>Team</td>
                <td>Score</td>
                <td>State</td>
                <td>Latest gate</td>
                <td>Time offset</td>
            </tr>
            </thead>
            <tbody>{listItems}</tbody>
        </Table>
    }

    displayTrackDetails() {
        if (this.tracks) {
            this.tracks.hideAllButThisTrack(this.state.displayTrack)
            this.tracks.showAnnotationsForTrack(this.state.displayTrack)
        }
        const events = this.state.displayTrack.contestant.scoreLog.map((line, index) => {
            return <li key={this.state.displayTrack.contestant.contestantNumber + "event" + index}>{line}</li>
        })
        return <div><h2>{this.state.displayTrack.contestant.displayString()}</h2>
            <ol>
                {events}
            </ol>
        </div>
    }

    displayTurningpointstanding() {
        if (this.tracks) {
            this.tracks.showAllTracks()
            this.tracks.hideAllAnnotations()
        }
        let scores = this.tracks.tracks.filter((c) => {
            return !Number.isNaN(c.contestant.getScoreByGate(this.state.turningPoint))
        })
        const minimumTurningpointscore = scores.reduce((min, p) => p.contestant.getScoreByGate(this.state.turningPoint) < min ? p.contestant.getScoreByGate(this.state.turningPoint) : min, 999999999);
        scores = scores.sort((a, b) => {
            if (a.contestant.getScoreByGate(this.state.turningPoint) > b.contestant.getScoreByGate(this.state.turningPoint)) return 1;
            if (a.contestant.getScoreByGate(this.state.turningPoint) < b.contestant.getScoreByGate(this.state.turningPoint)) return -1;
            return 0
        }).map((c) => {
            return <li
                key={this.state.turningPoint.name + "turningpoint" + c.contestant.contestantNumber}>{c.contestant.contestantNumber} {c.contestant.displayString()} with {getScore(this.state.scoreType, minimumTurningpointscore, c.contestant.getScoreByGate(this.state.turningPoint))}</li>
        })
        return <div><h2>{this.state.turningPoint}</h2>
            <ol>{scores}</ol>
        </div>
    }

    scoreTypeLink(scoreType) {
        const nextType = scoreTypeList[(scoreTypeList.indexOf(scoreType) + 1) % scoreTypeList.length]
        return <a href={"#"}
                  onClick={() => this.setState({scoreType: nextType})}>{ScoreTypeName[nextType]}</a>
    }

    render() {
        if (this.props.displayTable) {

            let displayLogo =
                <img src={"/static/img/AirSportsLogo.png"} className={"img-fluid float-right"}/>
            let detailsDisplay
            if (this.state.currentDisplay === DisplayTypes.scoreboard) {
                detailsDisplay = this.displayScoreboard()
            } else if (this.state.currentDisplay === DisplayTypes.simpleScoreboard) {
                detailsDisplay = this.displaySimpleScoreBoard()
            } else if (this.state.currentDisplay === DisplayTypes.trackDetails) {
                detailsDisplay = this.displayTrackDetails()
            } else if (this.state.currentDisplay === DisplayTypes.turningpointstanding) {
                detailsDisplay = this.displayTurningpointstanding()
            }
            let scorePerGate = <div className={"row"}>
                <div className={"col-12"}>
                    Scores per gate:<br/>
                    <ul className={"commaList"}>
                        {this.turningPointsDisplay}
                    </ul>
                </div>
            </div>

            return (
                <div className={"row"}>
                    <div className={"row"}>
                        <div className={"col-6"}>
                            {this.scoreTypeLink(this.state.scoreType)} | <a href={"#"}
                                                                            onClick={() => this.setState({currentDisplay: DisplayTypes.scoreboard})}> Detailed
                            table</a>
                        </div>
                    </div>
                    <div className={"row"}>
                        <div className={"col-6"}>
                            <h2><a href={"#"}
                                   onClick={() => this.setState({currentDisplay: DisplayTypes.simpleScoreboard})}>{this.contest.name}</a>
                            </h2>
                        </div>
                        <div className={"col-6"}>
                            {this.state.currentDisplay !== DisplayTypes.simpleScoreboard ? displayLogo : <div/>}
                        </div>
                    </div>
                    {this.state.currentDisplay !== DisplayTypes.simpleScoreboard ? scorePerGate : null}
                    <div className={"row fill"}>
                        <div className={"col-12 fill"}>
                            {
                                detailsDisplay
                            }
                        </div>
                    </div>

                </div>
            );
        }
        return <div/>
    }

}

