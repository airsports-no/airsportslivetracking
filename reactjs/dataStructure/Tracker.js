import {w3cwebsocket as W3CWebSocket} from "websocket";
import React from "react";
import {TraccarDevice, TraccarDeviceList} from "./TraccarDevices";
import {TraccarDeviceTracks} from "./ContestantTrack";
import axios from "axios";
import {circle, marker, polyline} from "leaflet"

export class Tracker extends React.Component {
    constructor(props) {
        super(props)
        this.contest = props.contest;
        this.startTime = new Date(this.contest.start_time)
        this.finishTime = new Date(this.contest.finish_time)
        this.liveMode = props.liveMode
        console.log(this.startTime)
        this.map = props.map;
        this.state = {score: {}, currentTime: new Date().toLocaleString()}
        this.initiateSession()
        this.renderTrack();
    }


    updateScoreCallback(contestant) {
        let existing = this.state.score;
        existing[contestant.contestantNumber] = contestant;
        this.setState({score: existing})
    }

    async initiateSession() {
        const result = await axios.get("http://" + this.contest.server_address + "/api/session?token=" + this.contest.server_token, {withCredentials: true})
        // Required to wait for the promise to resolve
        console.log(result)
        console.log("Initiated session")
        const devices_results = await axios.get("http://" + this.contest.server_address + "/api/devices", {withCredentials: true})
        console.log("Device data:")
        console.log(devices_results.data)
        const devices = devices_results.data.map((data) => {
            return new TraccarDevice(data.id, data.name, data.status, data.lastUpdate, data.category);
        })

        this.traccarDeviceList = new TraccarDeviceList(devices);
        this.traccarDeviceTracks = new TraccarDeviceTracks(this.traccarDeviceList, this.map, this.startTime, this.finishTime, this.contest.contestant_set, this.contest.track, (contestant) => this.updateScoreCallback(contestant));
        // Fetch history
        for (const track of this.traccarDeviceTracks.tracks) {
            console.log("Get history for " + track.traccarDevice.name)
            const res = await axios.get("http://" + this.contest.server_address + "/api/positions?deviceId=" + track.traccarDevice.id + "&from=" + this.startTime.toISOString() + "&to=" + this.finishTime.toISOString(), {withCredentials: true})
            await console.log(res.data)
            track.addPositionHistory(res.data)
            if (this.liveMode) track.insertHistoryIntoLiveTrack()
        }
        if (this.liveMode) {
            this.client = new W3CWebSocket("ws://" + this.contest.server_address + "/api/socket")

            this.client.onopen = () => {
                console.log("Client connected")
            };
            this.client.onmessage = (message) => {
                let data = JSON.parse(message.data);
                this.appendPositionReports(data);
            };
            setInterval(() => {
                this.setState({currentTime: new Date().toLocaleString})
            }, 1000)
        } else {
            console.log("Historic mode, rendering historic tracks")
            this.historicTimeStep = 2
            const interval = 1000
            this.currentHistoricTime = new Date(this.startTime.getTime() + this.historicTimeStep * interval)
            setInterval(() => {
                // console.log("Rendering historic time: " + this.currentHistoricTime)
                this.setState({currentTime: this.currentHistoricTime.toLocaleString()})
                this.traccarDeviceTracks.renderHistoricTime(this.currentHistoricTime)
                this.currentHistoricTime.setTime(this.currentHistoricTime.getTime() + this.historicTimeStep * interval)
            }, interval)
            // this.traccarDeviceTracks.renderHistoricTracks()
        }
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
            circle([waypoint.latitude, waypoint.longitude], {
                color: "blue"
            }).bindTooltip(waypoint.name, {permanent: true}).addTo(this.map)
        });
        this.contest.track.waypoints.filter((waypoint) => {
            return waypoint.is_procedure_turn
        }).map((waypoint) => {
            circle([waypoint.latitude, waypoint.longitude], {
                radius: 500,
                color: "blue"
            }).addTo(this.map)
        })
        let route = polyline(turningPoints, {
            color: "blue"
        }).addTo(this.map)
        this.map.fitBounds(route.getBounds(), {padding: [50, 50]})

    }

    appendPositionReports(data) {
        if (data.positions) {
            for (let position in data.positions) {
                this.traccarDeviceTracks.appendPositionReport(data.positions[position])
            }
        }
    }

    compareScore(a, b) {
        if (a.score > b.score) return 1;
        if (a.score < b.score) return -1;
        return 0
    }

    render() {
        let contestants = []
        for (const key in this.state.score) {
            if (this.state.score.hasOwnProperty(key)) {
                contestants.push(this.state.score[key])
            }
        }
        contestants.sort(this.compareScore)
        let position = 1
        const listItems = contestants.map((d) => <tr
            key={d.contestantNumber}>
            <td>{position++}</td>
            <td>{d.contestantNumber}</td>
            <td>{d.pilot}</td>
            <td>{d.score}</td>
            <td>{d.trackState}</td>
            <td>{d.latestStatus}</td>
            <td>{d.currentLeg}</td>
        </tr>);
        return (
            <div>
                <h1>{this.liveMode ? "Live" : "Historic"} contest tracking</h1>
                <h2>{this.contest.name}</h2>
                <h2>{this.state.currentTime}</h2>
                <table border={1}>
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
            </div>
        );
    }

}