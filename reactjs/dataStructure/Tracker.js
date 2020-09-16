import {w3cwebsocket as W3CWebSocket} from "websocket";
import React from "react";
import Cesium from 'cesium/Cesium';
import {TraccarDevice, TraccarDeviceList} from "./TraccarDevices";
import {TraccarDeviceTracks} from "./ContestantTrack";
import axios from "axios";

export class Tracker extends React.Component {
    constructor(props) {
        super(props)
        this.contest = props.contest;
        this.startTime = new Date(this.contest.start_time)
        this.finishTime = new Date(this.contest.finish_time)
        this.liveMode = new Date() < this.finishTime
        console.log(this.startTime)
        this.viewer = props.viewer;
        this.state = {score: {}}
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
        this.traccarDeviceTracks = new TraccarDeviceTracks(this.traccarDeviceList, this.viewer, this.startTime, this.finishTime, this.contest.contestant_set, this.contest.track, (contestant) => this.updateScoreCallback(contestant));
        // Fetch history
        for (const track of this.traccarDeviceTracks.tracks) {
            console.log("Get history for " + track.traccarDevice.name)
            const res = await axios.get("http://" + this.contest.server_address + "/api/positions?deviceId=" + track.traccarDevice.id + "&from=" + this.startTime.toISOString() + "&to=" + this.finishTime.toISOString(), {withCredentials: true})
            await console.log(res.data)
            track.addPositionHistory(res.data)
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
        }
    }

    renderTrack() {
        for (const key in this.contest.track.waypoints) {
            if (this.contest.track.waypoints.hasOwnProperty(key)) {
                let gate = this.contest.track.waypoints[key];
                this.viewer.entities.add(new Cesium.Entity({
                    name: name + "_gate",
                    polyline: {
                        positions: [new Cesium.Cartesian3.fromDegrees(gate.gate_line[0], gate.gate_line[1]), new Cesium.Cartesian3.fromDegrees(gate.gate_line[2], gate.gate_line[3])],
                        width: 2,
                        material: Cesium.Color.BLUEVIOLET
                    }

                }));
            }
        }
        let turningPoints = this.contest.track.waypoints.filter((waypoint) => {
            return waypoint.type === "tp"
        }).map((waypoint) => {
            return Cesium.Cartesian3.fromDegrees(waypoint.longitude, waypoint.latitude)
        });
        this.contest.track.waypoints.map((waypoint) => {
            this.viewer.entities.add(new Cesium.Entity({
                name: waypoint.name,
                position: Cesium.Cartesian3.fromDegrees(waypoint.longitude, waypoint.latitude),
                // point: {
                //     pixelSize: 4,
                //     color: Cesium.Color.WHITE,
                //     outlineColor: Cesium.Color.WHITE,
                //     outlineWidth: 2
                // },
                label: {
                    text: waypoint.name,
                    font: '14pt monospace',
                    outlineWidth: 2,
                    verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                    pixelOffset: new Cesium.Cartesian2(0, -9)
                }

            }))
        });

        this.trackEntity = this.viewer.entities.add({
            name: this.contest.name + "_track",
            polyline: {
                positions: turningPoints,
                width: 2,
                material: Cesium.Color.BLUEVIOLET
            }
        })
        this.viewer.flyTo(this.trackEntity);
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
        const listItems = contestants.map((d) => <li
            key={d.contestantNumber}>{d.contestantNumber} {d.pilot} {d.score}</li>);
        return (
            <div>
                <h1>{this.liveMode ? "Live" : "Historic"} contest tracking</h1>
                <h2>{this.contest.name}</h2>
                <ol>{listItems}</ol>
            </div>
        );
    }

}