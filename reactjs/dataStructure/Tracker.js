import {w3cwebsocket as W3CWebSocket} from "websocket";
import React from "react";
import Cesium from 'cesium/Cesium';
import {TraccarDeviceList} from "./TraccarDevices";
import {TraccarDeviceTracks} from "./ContestantTrack";
import axios from "axios";
import {server, token} from "./constants";

export class Tracker extends React.Component {
    constructor(props) {
        super(props)
        this.contest = props.contest;
        this.viewer = props.viewer;
        this.state = {score: {}}
        this.traccarDeviceList = new TraccarDeviceList();
        this.traccarDeviceTracks = new TraccarDeviceTracks(this.traccarDeviceList, this.viewer, new Date(this.contest.startTime), new Date(this.contest.finishTime), this.contest.contestant_set, this.contest.track, (contestant) => this.updateScoreCallback(contestant));
        this.initiateSession()
        this.renderTrack();
    }

    updateScoreCallback(contestant) {
        let existing = this.state.score;
        existing[contestant.contestantNumber] = contestant;
        this.setState({score: existing})
    }

    initiateSession() {
        axios.get("http://" + server + "/api/session?token=" + token, {withCredentials: true}).then(res => {
            this.client = new W3CWebSocket("ws://" + server + "/api/socket")
            console.log("Initiated session")
            console.log(res)

            this.client.onopen = () => {
                console.log("Client connected")
            };
            this.client.onmessage = (message) => {
                let data = JSON.parse(message.data);
                this.appendPositionReports(data);
            };

        })
    }

    renderTrack() {
        for (const key in this.contest.track.gates) {
            if (this.contest.track.gates.hasOwnProperty(key)) {
                let gate = this.contest.track.gates[key];
                this.viewer.entities.add(new Cesium.Entity({
                    name: name + "_gate",
                    polyline: {
                        positions: [new Cesium.Cartesian3.fromDegrees(gate[0], gate[1]), new Cesium.Cartesian3.fromDegrees(gate[2], gate[3])],
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
                <h1>Live contest tracking</h1>
                <h2>{this.contest.name}</h2>
                <ol>{listItems}</ol>
            </div>
        );
    }

}