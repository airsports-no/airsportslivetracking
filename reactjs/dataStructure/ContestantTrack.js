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
import {fractionOfLeg, intersect} from "./lineUtilities";
import {ScoreCalculator} from "./scoreCalculator"


class Gate {
    constructor(name, x1, y1, x2, y2, expectedTime) {
        this.name = name
        this.x1 = x1
        this.y1 = y1
        this.x2 = x2
        this.y2 = y2
        this.passingTime = -1
        this.missed = false
        this.expectedTime = expectedTime
    }

}

export class PositionReport {
    constructor(latitude, longitude, altitude, batteryLevel, deviceTime, serverTime, speed, course) {
        this.latitude = latitude
        this.longitude = longitude
        this.altitude = altitude
        this.batteryLevel = batteryLevel
        this.deviceTime = new Date(deviceTime)
        this.serverTime = new Date(serverTime)
        this.speed = speed
        this.course = course
        this.cartesian = Cesium.Cartesian3.fromDegrees(this.longitude, this.latitude)
    }
}

function compare(a, b) {
    if (a.deviceTime > b.deviceTime) return 1;
    if (a.deviceTime < b.deviceTime) return -1;
    return 0
}

export class ContestantTrack {
    constructor(traccarDevice, viewer, contestant, track, updateScoreCallback, startTime, finishTime) {
        this.traccarDevice = traccarDevice;
        this.updateScoreCallback = updateScoreCallback
        this.startTime = startTime
        this.finishTime = finishTime
        this.contestant = contestant
        this.track = track
        this.positions = []
        this.viewer = viewer;
        this.gates = []
        this.latestPositionRendered = 0
        for (const index in this.track.waypoints) {
            const gate = this.track.waypoints[index]
            this.gates.push(new Gate(gate.name, gate.gate_line[0], gate.gate_line[1], gate.gate_line[2], gate.gate_line[3], new Date(this.contestant.gate_times[gate.name])))
        }
        this.outstandingGates = Array.from(this.gates)
        this.updateScoreCallback(this.contestant)
        this.scoreCalculator = new ScoreCalculator(this)
        this.lineCollection = null;
        this.dot = null;
    }

    createLiveEntities() {
        this.lineCollection = this.viewer.scene.primitives.add(new Cesium.PolylineCollection())
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
    }

    createPolyline(positions) {
        let material = new Cesium.Material.fromType("Color")
        material.uniforms.color = Cesium.Color.fromCssColorString(this.contestant.colour)
        this.lineCollection.add({
            positions: positions,
            width: 2,
            material: material
        })

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
        if (crossedGate) {
            this.scoreCalculator.updateGateScore()
            this.contestant.score = this.scoreCalculator.getScore()
            this.updateScoreCallback(this.contestant)
        }
    }

    appendPosition(positionReport, render) {
        // console.log("Added position for " + this.traccarDevice.name + " :")
        // console.log(positionReport)
        let a = new PositionReport(positionReport.latitude, positionReport.longitude, positionReport.altitude, positionReport.attributes.batteryLevel, new Date(positionReport.deviceTime), new Date(positionReport.serverTime), positionReport.speed, positionReport.course);
        if (!(this.contestant.takeOffTime < a.deviceTime < this.contestant.finishedByTime)) {
            // console.log("Ignoring old message for " + this.traccarDevice.name)
            return
        }
        // console.log(a)
        this.positions.push(a);
        if (render) {
            this.renderPositions();
        }
        this.checkIntersections()
    }

    addPositionHistory(positions) {
        // To be called only at the beginning, before we start receiving live positions
        this.positions = []
        for (const positionReport of positions) {
            this.appendPosition(positionReport, false)
        }
        this.checkIntersections()
    }

    renderPositions() {
        if (!this.dot) {
            this.createLiveEntities()
        }
        this.positions.sort(compare);
        let b = this.positions.slice(this.latestPositionRendered - this.positions.length)
        if (b.length) {
            // So that the next time we render the two last positions in order to get a line
            this.latestPositionRendered = this.positions.length - 1
            let newest_position = b.slice(-1)[0].cartesian;
            if (b.length > 1) {
                this.createPolyline(b.map((position) => {
                    return position.cartesian
                }));
            }
            this.dot.position = newest_position
        }
    }

    renderHistoricPositions() {
        // Used in non-live mode to render the track relative to contest start including timing information so that
        // we can use the cesium timing controls for playback
        let localTrack = new Cesium.SampledPositionProperty()
        if (this.positions.length > 0) {
            const firstPositionTime = this.positions[0].deviceTime
            for (const position of this.positions) {
                localTrack.addSample(
                    // Make all tracks start at the beginning of the contest time for historic playback
                    Cesium.JulianDate.fromDate(new Date(this.startTime.getTime() + (position.deviceTime - firstPositionTime))),
                    position.cartesian
                );
            }
        }
        let material = new Cesium.Material.fromType("Color")
        material.uniforms.color = Cesium.Color.fromCssColorString(this.contestant.colour)
        this.historicTrack = this.viewer.entities.add({
            position: localTrack,
            name: this.contestant.id + "_path",
            path: {
                show: true,
                resolution: 1,
                material: Cesium.Color.fromCssColorString(this.contestant.colour),
                width: 2,
                leadTime: 0,
                trailTime: (this.finishTime - this.startTime) / 1000
            },
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
    }

    createCartesianPositionList(fromIndex) {
        return this.positions.slice(fromIndex - this.positions.length).map((position) => {
            return Cesium.Cartesian3.fromDegrees(position.longitude, position.latitude)
        })
    }


}

export class TraccarDeviceTracks {
    constructor(traccarDeviceList, viewer, startTime, finishTime, contestantList, track, updateScoreCallback) {
        this.updateScoreCallback = updateScoreCallback
        this.startTime = startTime;
        this.finishTime = finishTime;
        this.track = track;
        this.contestants = new ContestantList(contestantList)
        this.traccarDeviceList = traccarDeviceList;
        this.viewer = viewer
        this.tracks = []
        this.prePopulateContestantTracks()
    }


    prePopulateContestantTracks() {
        this.contestants.contestants.forEach(contestant => {
            const track = new ContestantTrack(this.getTrackerForContestant(contestant), this.viewer, contestant, this.track, this.updateScoreCallback, this.startTime, this.finishTime);
            this.tracks.push(track);
        })
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
            track = new ContestantTrack(traccarDevice, this.viewer, contestant, this.track, this.updateScoreCallback, this.startTime, this.finishTime);
            this.tracks.push(track);
        }
        return track;
    }

    appendPositionReport(positionReport) {
        let device = this.traccarDeviceList.deviceById(positionReport.deviceId);
        let track = this.getTrackForTraccarDevice(device, new Date(positionReport.deviceTime));
        if (track)
            track.appendPosition(positionReport, true);
    }

    getTrackerForContestant(contestant) {
        return this.traccarDeviceList.deviceByName(contestant.trackerName)
    }

    renderHistoricTracks() {
        this.tracks.forEach(track => {
            track.renderHistoricPositions()
        })
    }
}