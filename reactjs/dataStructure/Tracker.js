import React from "react";
import {ContestantTracks} from "./ContestantTrack";
import axios from "axios";
import {circle, divIcon, marker, polyline} from "leaflet"

const DisplayTypes = {
    scoreboard: 0,
    trackDetails: 1,
    turningpointstanding: 2
}

export class Tracker extends React.Component {
    constructor(props) {
        super(props)
        this.contest = props.contest;
        this.startTime = new Date(this.contest.start_time)
        this.finishTime = new Date(this.contest.finish_time)
        this.lastDataTime = {}
        this.liveMode = props.liveMode
        this.map = props.map;
        this.tracks = new ContestantTracks(this.map, this.startTime, this.finishTime, this.contest.contestant_set, this.contest.track, (contestant) => this.updateScoreCallback(contestant));
        this.state = {score: {}, currentTime: new Date().toLocaleString(), currentDisplay: DisplayTypes.scoreboard}
        this.turningPointsDisplay = this.contest.track.waypoints.map((waypoint) => {
            return <a href={"#"} onClick={() => {
                this.setState({currentDisplay: DisplayTypes.turningpointstanding, turningPoint: waypoint.name})
            }} key={"tplist" + waypoint.name}>{waypoint.name}, </a>
        })
        this.renderTrack();
        this.fetchNextData();
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


    render() {
        let detailsDisplay
        if (this.state.currentDisplay === DisplayTypes.scoreboard) {
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
            let position = 1
            const listItems = contestants.map((d) => <tr
                key={"leaderboard" + d.contestantNumber}>
                <td>{position++}</td>
                <td><a href={"#"}
                       onClick={() => this.setState({
                           currentDisplay: DisplayTypes.trackDetails,
                           displayTrack: this.tracks.getTrackForContestant(d.id)
                       })}>{d.contestantNumber}</a></td>
                <td>{d.displayString()}</td>
                <td>{d.score}</td>
                <td>{d.trackState}</td>
                <td>{d.latestStatus}</td>
                <td>{d.currentLeg}</td>
            </tr>);
            detailsDisplay = <table border={1}>
                <thead>
                <tr>
                    <td>Rank</td>
                    <td>#</td>
                    <td>Pilot</td>
                    <td>Score</td>
                    <td>Tracking state</td>
                    <td>Latest event</td>
                    <td>Current leg</td>
                </tr>
                </thead>
                <tbody>{listItems}</tbody>
            </table>
        } else if (this.state.currentDisplay === DisplayTypes.trackDetails) {
            if (this.tracks) {
                this.tracks.hideAllButThisTrack(this.state.displayTrack)
                this.tracks.showAnnotationsForTrack(this.state.displayTrack)
            }
            const events = this.state.displayTrack.contestant.scoreLog.map((line, index) => {
                return <li key={this.state.displayTrack.contestant.contestantNumber + "event" + index}>{line}</li>
            })
            detailsDisplay = <div><h2>{this.state.displayTrack.contestant.displayString()}</h2>
                <ol>
                    {events}
                </ol>
            </div>
        } else if (this.state.currentDisplay === DisplayTypes.turningpointstanding) {
            if (this.tracks) {
                this.tracks.showAllTracks()
                this.tracks.hideAllAnnotations()
            }
            const scores = this.tracks.tracks.filter((c) => {
                return !Number.isNaN(c.contestant.getScoreByGate(this.state.turningPoint))
            }).sort((a, b) => {
                if (a.contestant.getScoreByGate(this.state.turningPoint) > b.contestant.getScoreByGate(this.state.turningPoint)) return 1;
                if (a.contestant.getScoreByGate(this.state.turningPoint) < b.contestant.getScoreByGate(this.state.turningPoint)) return -1;
                return 0
            }).map((c) => {
                return <li
                    key={this.state.turningPoint.name + "turningpoint" + c.contestant.contestantNumber}>{c.contestant.contestantNumber} {c.contestant.displayString()} with {c.contestant.getScoreByGate(this.state.turningPoint)} points</li>
            })
            detailsDisplay = <div><h2>{this.state.turningPoint}</h2>
                <ol>{scores}</ol>
            </div>
        }
        return (
            <div>
                <h1>{this.liveMode ? "Live" : "Historic"} contest tracking</h1>
                <h2><a href={"#"}
                       onClick={() => this.setState({currentDisplay: DisplayTypes.scoreboard})}>{this.contest.name}</a>
                </h2>
                <h2>{this.state.currentTime}</h2>
                {this.turningPointsDisplay}
                {detailsDisplay}
            </div>
        );
    }

}