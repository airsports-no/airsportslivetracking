import {ContestantList} from "./Contestants";
import {fractionOfLeg, intersect} from "./lineUtilities";
import {ScoreCalculator} from "./scoreCalculator"
import {circle, marker, polyline} from "leaflet"


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
    }
}

function compare(a, b) {
    if (a.deviceTime > b.deviceTime) return 1;
    if (a.deviceTime < b.deviceTime) return -1;
    return 0
}

export class ContestantTrack {
    constructor(traccarDevice, map, contestant, track, updateScoreCallback, startTime, finishTime) {
        this.traccarDevice = traccarDevice;
        this.updateScoreCallback = updateScoreCallback
        this.startTime = startTime
        this.finishTime = finishTime
        this.contestant = contestant
        this.track = track
        this.positions = []
        this.historicPositions = []
        this.map = map;
        this.gates = []
        this.lastRenderedTime = this.startTime
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

    createLiveEntities(position) {
        this.lineCollection = polyline([position], {
            color: this.contestant.colour
        }).addTo(this.map)
        this.dot = marker(position, {
            color: this.contestant.colour
        }).bindTooltip(this.contestant.pilot, {
            permanent: true
        }).addTo(this.map)
    }

    createPolyline(positions) {
        positions.map((position) => {
            this.lineCollection.addLatLng(position)
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
            this.renderPositions(this.positions.slice(-Math.min(2, this.positions.length)));
        }
        this.checkIntersections()
    }

    addPositionHistory(positions) {
        this.historicPositions = positions
    }
    insertHistoryIntoLiveTrack(){
        this.positions = []
        // To be called only at the beginning, before we start receiving live positions
        for (const positionReport of this.historicPositions) {
            this.appendPosition(positionReport, false)
        }
        this.renderPositions(this.positions)
    }

    renderPositions(positions) {
        let b = positions
        if (b.length) {
            let newest_position = b.slice(-1)[0];
            const newest_position_coordinates = [newest_position.latitude, newest_position.longitude]
            if (!this.dot) {
                this.createLiveEntities(newest_position_coordinates)
            } else {
                this.dot.setLatLng(newest_position_coordinates)
            }
            if (b.length > 1) {
                this.createPolyline(b.map((position) => {
                    return [position.latitude, position.longitude]
                }));
            }
        }
    }

    renderHistoricTime(historicTime) {
        if (!this.historicPositions.length) return
        // historicPositions is the raw data, not wrapped into the appropriate class
        const initialTrackTime = new Date(this.historicPositions[0].deviceTime)
        const toRender = this.historicPositions.filter((position) => {
            const shiftedStartTime = new Date(this.startTime.getTime() + (new Date(position.deviceTime) - initialTrackTime))
            return this.lastRenderedTime < shiftedStartTime && shiftedStartTime <= historicTime
        })
        console.log(this.contestant.pilot + ": Last rendered is " + this.lastRenderedTime + ", rendering until " + historicTime + ": " + toRender.length)
        toRender.map((position)=>{
            this.appendPosition(position, true)
        })
        this.lastRenderedTime = new Date(historicTime.getTime())
    }

}

export class TraccarDeviceTracks {
    constructor(traccarDeviceList, map, startTime, finishTime, contestantList, track, updateScoreCallback) {
        this.updateScoreCallback = updateScoreCallback
        this.startTime = startTime;
        this.finishTime = finishTime;
        this.track = track;
        this.contestants = new ContestantList(contestantList)
        this.traccarDeviceList = traccarDeviceList;
        this.map = map
        this.tracks = []
        this.prePopulateContestantTracks()
    }


    prePopulateContestantTracks() {
        this.contestants.contestants.forEach(contestant => {
            const track = new ContestantTrack(this.getTrackerForContestant(contestant), this.map, contestant, this.track, this.updateScoreCallback, this.startTime, this.finishTime);
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
            track = new ContestantTrack(traccarDevice, this.map, contestant, this.track, this.updateScoreCallback, this.startTime, this.finishTime);
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


    renderHistoricTime(historicTime) {
        this.tracks.map((track) => {
            track.renderHistoricTime(historicTime)
        })
    }
}