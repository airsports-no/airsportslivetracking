// {
//   "id": 17,
//   "attributes": {
//     "batteryLevel": 44,
//     "distance": 3233.47,
//     "totalDistance": 39108.49,
//     "motion": false
//   },
//   "deviceId": 1,
//   "type": null,
//   "protocol": "osmand",
//   "serverTime": "2020-09-07T18:15:24.344+0000",
//   "deviceTime": "2020-09-07T18:15:22.000+0000",
//   "fixTime": "2020-09-07T18:15:22.000+0000",
//   "outdated": false,
//   "valid": true,
//   "latitude": 60.3997898,
//   "longitude": 11.2167158,
//   "altitude": 0,
//   "speed": 0,
//   "course": 90,
//   "address": null,
//   "accuracy": 2799.9990234375,
//   "network": null
// }


import Cesium from 'cesium/Cesium';

import {ContestantList} from "./Contestants";
import axios from "axios";
import {protocol, server} from "./constants";
import {fractionOfLeg, intersect} from "./lineUtilities";

class Gate {
    constructor(name, x1, y1, x2, y2) {
        this.name = name
        this.x1 = x1
        this.y1 = y1
        this.x2 = x2
        this.y2 = y2
        this.passingTime = -1
        this.missed = false
    }

}

export class PositionReport {
    constructor(latitude, longitude, altitude, batteryLevel, deviceTime, serverTime, speed, course) {
        this.latitude = latitude
        this.longitude = longitude
        this.altitude = altitude
        this.batteryLevel = batteryLevel
        this.deviceTime = deviceTime
        this.serverTime = serverTime
        this.speed = speed
        this.course = course
    }
}

function compare(a, b) {
    if (a.deviceTime > b.deviceTime) return 1;
    if (a.deviceTime < b.deviceTime) return -1;
    return 0
}

export class ContestantTrack {
    constructor(traccarDevice, viewer, contestant, track, updateScoreCallback) {
        this.traccarDevice = traccarDevice;
        this.updateScoreCallback = updateScoreCallback
        this.contestant = contestant
        this.track = track
        this.positions = [];
        this.viewer = viewer;
        this.gates = []
        for (const index in this.track.waypoints) {
            let name = this.track.waypoints[index].name
            if (this.track.gates.hasOwnProperty(name)) {
                let gate = this.track.gates[name];
                this.gates.push(new Gate(name, gate[0], gate[1], gate[2], gate[3]))
            }
        }
        this.outstandingGates = Array.from(this.gates)
        this.polyline = this.viewer.entities.add({
            name: this.traccarDevice.name + "_line",
            polyline: {
                positions: [],
                width: 2,
                material: Cesium.Color.fromCssColorString(this.contestant.colour)
            }
        })
        this.dot = this.viewer.entities.add({
            name: this.traccarDevice.name,
            position: Cesium.Cartesian3.fromDegrees(0, 0),
            point: {
                pixelSize: 5,
                color: Cesium.Color.RED,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2
            },
            label: {
                text: this.contestant.pilot,
                font: '14pt monospace',
                outlineWidth: 2,
                verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                pixelOffset: new Cesium.Cartesian2(0, -9)
            }

        })
        this.updateScoreCallback(this.contestant)
    }

    getPositionsHistory() {

        axios.get(protocol + "://" + server + "/api/positions?deviceId=" + this.traccarDevice.id, {withCredentials: true}).then(res => {

        });
    }

    getTimeOfIntersectLastPosition(gate) {
        if (this.positions.length > 1) {
            let segment = this.positions.slice(-2);
            let intersection = intersect(segment[0].longitude, segment[0].latitude, segment[1].longitude, segment[1].latitude, gate.x1, gate.y1, gate.x2, gate.y2)
            if (intersection) {
                let fraction = fractionOfLeg(segment[0].longitude, segment[0].latitude, segment[1].longitude, segment[1].latitude, intersection.x, intersection.y)
                let timeDifference = segment[1].deviceTime - segment[0].deviceTime
                return new Date(segment[0].deviceTime.getTime() + fraction * timeDifference);
            }
        }
        return false
    }

    checkIntersections() {
        let i = this.outstandingGates.length
        let crossedGate = false
        while (i--) {
            let intersectionTime = this.getTimeOfIntersectLastPosition(this.outstandingGates[i])
            if (intersectionTime) {
                console.log("Intersected gate " + this.outstandingGates[i].name + " at time " + intersectionTime)
                this.outstandingGates[i].passingTime = intersectionTime
                crossedGate = true;
            }
            if (crossedGate) {
                if (this.outstandingGates[i].passingTime === -1) {
                    this.outstandingGates[i].missed = true
                console.log("Missed gate " + this.outstandingGates[i].name)
                }
                this.outstandingGates.splice(i, 1);
            }
        }
    }

    appendPosition(positionReport) {
        // console.log("Added position for " + this.traccarDevice.name + " :")
        // console.log(positionReport)
        let a = new PositionReport(positionReport.latitude, positionReport.longitude, positionReport.altitude, positionReport.attributes.batteryLevel, new Date(positionReport.deviceTime), new Date(positionReport.serverTime), positionReport.speed, positionReport.course);
        if (a.deviceTime < this.contestant.startTime) {
            // console.log("Ignoring old message for " + this.traccarDevice.name)
            return
        }
        // console.log(a)
        this.positions.push(a);
        this.positions.sort(compare);
        // console.log("Current list")
        // console.log(this.positions);
        let b = this.createCartesianPositionList();
        let newest_position = b.slice(-1)[0];
        this.polyline.polyline.positions = b
        this.dot.position = newest_position
        this.checkIntersections()
    }

    createCartesianPositionList() {
        return this.positions.map((position) => {
            return Cesium.Cartesian3.fromDegrees(position.longitude, position.latitude)
        })
    }


}

export class TraccarDeviceTracks {
    constructor(traccarDeviceList, viewer, startDate, finishDate, contestantList, track, updateScoreCallback) {
        this.updateScoreCallback = updateScoreCallback
        this.startDate = startDate;
        this.finishDate = finishDate;
        this.track = track;
        this.contestants = new ContestantList(contestantList)
        this.traccarDeviceList = traccarDeviceList;
        this.viewer = viewer
        this.tracks = []
    }


    getTrackForTraccarDevice(traccarDevice, atTime) {
        let contestant = this.contestants.getContestantForTrackerForTime(traccarDevice.name, atTime)
        if (!contestant) {
            console.log("Found no contestant for device " + traccarDevice.name + " at time " + atTime)
            return null;
        }
        let track = this.tracks.find((track) => track.contestant.id === contestant.id)
        if (!track) {
            console.log("Created new track for " + traccarDevice.name)
            track = new ContestantTrack(traccarDevice, this.viewer, contestant, this.track, this.updateScoreCallback);
            this.tracks.push(track);
        }
        return track;
    }

    appendPositionReport(positionReport) {
        let device = this.traccarDeviceList.deviceById(positionReport.deviceId);
        let track = this.getTrackForTraccarDevice(device, new Date(positionReport.deviceTime));
        if (track)
            track.appendPosition(positionReport);
    }


}