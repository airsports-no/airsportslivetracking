import {ContestantList} from "./Contestants";
import {ScoreCalculator} from "./scoreCalculator"
import {divIcon, layerGroup, marker, polyline} from "leaflet"
import {getDistance, sleep} from "./utilities";
import {informationAnnotationIcon} from "./iconDefinitions";


class Gate {
    constructor(gate, expectedTime) {
        this.name = gate.name
        this.x1 = gate.gate_line[0]
        this.y1 = gate.gate_line[1]
        this.x2 = gate.gate_line[2]
        this.y2 = gate.gate_line[3]
        this.latitude = gate.latitude
        this.longitude = gate.longitude
        this.insideDistance = gate.insideDistance
        this.outsideDistance = gate.outsideDistance
        this.isTurningPoint = gate.type === "tp"
        if (this.isTurningPoint) {
            this.distance = gate.distance
            this.bearing = gate.bearing
            this.isProcedureTurn = gate.is_procedure_turn
            this.turnDirection = gate.turn_direction
        }
        this.passingTime = -1
        this.missed = false
        this.expectedTime = expectedTime
    }

    hasBeenPassed() {
        return this.missed || this.passingTime !== -1
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
    constructor(traccarDevice, map, contestant, track, startTime, finishTime) {
        this.traccarDevice = traccarDevice;
        this.startTime = startTime
        this.finishTime = finishTime
        this.contestant = contestant
        this.track = track
        this.positions = []
        this.historicPositions = []
        this.map = map;
        this.gates = []
        this.displayed = false
        this.displayAnnotations = false
        this.lastRenderedTime = this.startTime
        for (const index in this.track.waypoints) {
            const gate = this.track.waypoints[index]
            this.gates.push(new Gate(gate, new Date(this.contestant.gate_times[gate.name])))
        }
        this.startingLine = new Gate(this.track.starting_line, new Date(this.contestant.gate_times[this.track.waypoints[0].name]))
        this.startingLinePassingTimes = [];
        this.contestant.updateScore(0)
        this.contestant.updateLatestStatus("")
        this.scoreCalculator = new ScoreCalculator(this)
        this.lineCollection = null;
        this.dot = null;
        this.annotationLayer = layerGroup()
        const size = 24;
        this.airplaneIcon = divIcon({
            html: '<i class="fa fa-plane" style="color: ' + this.contestant.colour + '"><br/>' + this.contestant.displayString() + '</i>',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })
    }


    createLiveEntities(positions) {
        const newest_position = positions.slice(-1)[0];

        this.lineCollection = polyline(positions, {
            color: this.contestant.colour
        })
        this.dot = marker(newest_position, {icon: this.airplaneIcon}).bindTooltip(this.contestant.displayFull(), {
            permanent: false
        })
        this.showTrack()
    }

    addAnnotation(latitude, longitude, message, icon) {
        if (icon == undefined) icon = informationAnnotationIcon
        this.annotationLayer.addLayer(marker([latitude, longitude], {icon: icon}).bindTooltip(message, {
            permanent: false
        }))
    }

    showAnnotations() {
        if (!this.displayAnnotations) {
            this.annotationLayer.addTo(this.map)
            this.displayAnnotations = true
        }
    }

    hideAnnotations() {
        if (this.displayAnnotations) {
            this.annotationLayer.removeFrom(this.map)
            this.displayAnnotations = false
        }
    }

    showTrack() {
        if (!this.displayed && this.dot) {
            this.lineCollection.addTo(this.map)
            this.dot.addTo(this.map)
            // this.map.addLayer(this.lineCollection)
            // this.map.addLayer(this.dot)
            this.displayed = true
        }
    }

    hideTrack() {
        if (this.displayed && this.dot) {
            this.lineCollection.removeFrom(this.map)
            this.dot.removeFrom(this.map)
            this.displayed = false
        }
    }

    createPolyline(positions) {
        positions.map((position) => {
            this.lineCollection.addLatLng(position)
        })
    }


    appendPosition(positionReport, render) {
        // TODO
        // if (this.contestant.pilot !== "Steinar") return
        let a = new PositionReport(positionReport.latitude, positionReport.longitude, positionReport.altitude, positionReport.attributes.batteryLevel, new Date(positionReport.deviceTime), new Date(positionReport.serverTime), positionReport.speed, positionReport.course);
        if (!(this.contestant.takeOffTime < a.deviceTime < this.contestant.finishedByTime)) {
            return
        }
        this.positions.push(a);
        if (render) {
            this.renderPositions(this.positions.slice(-1));
        }
        this.scoreCalculator.updateFinalScore()
    }

    addPositionHistory(positions) {
        this.historicPositions = positions
    }

    insertHistoryIntoLiveTrack() {
        this.positions = []
        // To be called only at the beginning, before we start receiving live positions
        for (const positionReport of this.historicPositions) {
            this.appendPosition(positionReport, false)
        }
        this.renderPositions(this.positions)
    }

    renderPositions(positions) {
        let b = positions.map((p) => {
            return [p.latitude, p.longitude]
        })
        if (b.length) {
            if (!this.dot) {
                this.createLiveEntities(b)
            } else {
                this.dot.setLatLng(newest_position_coordinates)
                b.map((position) => {
                    this.lineCollection.addLatLng(position)
                })
            }
        }
    }

    renderHistoricTime(historicTime) {
        if (!this.historicPositions.length) return
        // historicPositions is the raw data, not wrapped into the appropriate class
        const initialTrackTime = new Date(this.historicPositions[0].deviceTime)
        // todo
        const startTakeoffDifference = 0//this.contestant.takeoffTime - initialTrackTime
        const toRender = this.historicPositions.filter((position) => {
            const shiftedStartTime = new Date(this.startTime.getTime() + (new Date(position.deviceTime) - initialTrackTime) + startTakeoffDifference)
            return this.lastRenderedTime < shiftedStartTime && shiftedStartTime <= historicTime
        })
        // console.log(this.contestant.pilot + ": Last rendered is " + this.lastRenderedTime + ", rendering until " + historicTime + ": " + toRender.length)
        toRender.map((position) => {
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
        this.contestants = new ContestantList(contestantList, updateScoreCallback)
        this.traccarDeviceList = traccarDeviceList;
        this.map = map
        this.tracks = []
        this.prePopulateContestantTracks()
    }


    prePopulateContestantTracks() {
        this.contestants.contestants.forEach(contestant => {
            const track = new ContestantTrack(this.getTrackerForContestant(contestant), this.map, contestant, this.track, this.startTime, this.finishTime);
            this.tracks.push(track);
        })
    }

    getTrackForContestant(contestant) {
        return this.tracks.find((track) => track.contestant.id === contestant.id)
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
            track = new ContestantTrack(traccarDevice, this.map, contestant, this.track, this.startTime, this.finishTime);
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
            console.log(track.contestant.displayString())
            track.renderHistoricTime(historicTime)
        })
    }

    hideAllButThisTrack(track) {
        this.tracks.map((t) => {
            if (track !== t) {
                t.hideTrack()
            }
        })
    }

    showAnnotationsForTrack(track) {
        this.tracks.map((t) => {
            if (track === t) {
                t.showAnnotations()
            }
        })
    }

    hideAllAnnotations() {
        this.tracks.map((t) => {
            t.hideAnnotations()
        })
    }

    showAllTracks() {
        this.tracks.map((t) => {
            t.showTrack()
        })
    }
}