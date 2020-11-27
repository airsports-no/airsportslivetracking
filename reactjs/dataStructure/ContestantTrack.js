import {ContestantList} from "./Contestants";
import {ScoreCalculator} from "./scoreCalculator"
import 'leaflet'
import 'leaflet.markercluster'
import {getDistance, pz, sleep} from "./utilities";
import {anomalyAnnotationIcon, informationAnnotationIcon} from "./iconDefinitions";
import "leaflet.markercluster/dist/MarkerCluster.css"
import "leaflet.markercluster/dist/MarkerCluster.Default.css"

const L = window['L']

class Gate {
    constructor(gate, expectedTime) {
        this.name = gate.name
        this.x1 = gate.gate_line[0]
        this.y1 = gate.gate_line[1]
        this.x2 = gate.gate_line[2]
        this.y2 = gate.gate_line[3]
        this.latitude = gate.latitude
        this.longitude = gate.longitude
        this.insideDistance = gate.inside_distance
        this.outsideDistance = gate.outside_distance
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

class TrackRenderer {
    constructor(map, contestantTrack) {
        this.map = map
        this.contestantTrack = contestantTrack
        this.displayed = false
        this.displayAnnotations = false
        this.markers = L.markerClusterGroup()
        this.lineCollection = null;
        this.dot = null;
        this.annotationLayer = L.layerGroup()
        const size = 24;
        this.airplaneIcon = L.divIcon({
            html: '<i class="fa fa-plane" style="color: ' + this.contestantTrack.contestant.colour + '"><br/>' + this.contestantTrack.contestant.paddedContestantNumber  + ' ' + this.contestantTrack.contestant.displayString() + '</i>',
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2],
            className: "myAirplaneIcon"
        })
        this.iconMap = {
            anomaly: anomalyAnnotationIcon, information: informationAnnotationIcon
        }

    }

    //private
    createLiveEntities(positions) {
        const newest_position = positions.slice(-1)[0];

        this.lineCollection = L.polyline(positions, {
            color: this.contestantTrack.contestant.colour
        })
        this.dot = L.marker(newest_position, {icon: this.airplaneIcon}).bindTooltip(this.contestantTrack.contestant.displayFull(), {
            permanent: false
        })
        this.showTrack()
    }

    renderAnnotations(annotations) {
        annotations.map((annotation) => {
            this.addAnnotation(annotation.latitude, annotation.longitude, annotation.message, this.iconMap[annotation.type])
        })
    }

    addAnnotation(latitude, longitude, message, icon) {
        if (icon == undefined) icon = informationAnnotationIcon
        this.markers.addLayer(L.marker([latitude, longitude], {icon: icon}).bindTooltip(message, {
            permanent: false
        }))
    }

    showAnnotations() {
        if (!this.displayAnnotations) {
            this.markers.addTo(this.map)
            this.displayAnnotations = true
        }
    }

    hideAnnotations() {
        if (this.displayAnnotations) {
            this.markers.removeFrom(this.map)
            this.displayAnnotations = false
        }
    }

    showTrack() {
        if (!this.displayed && this.dot) {
            this.lineCollection.addTo(this.map)
            this.dot.addTo(this.map)
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


    renderPositions(b) {
        if (b.length) {
            if (!this.dot) {
                this.createLiveEntities(b)
            } else {
                this.dot.setLatLng(b.slice(-1)[0])
                b.map((position) => {
                    this.lineCollection.addLatLng(position)
                })
            }
        }
    }
}

export class ContestantTrack {
    constructor(map, contestant, track, startTime, finishTime) {
        this.startTime = startTime
        this.finishTime = finishTime
        this.contestant = contestant
        this.track = track
        this.positions = []
        this.historicPositions = []
        if (map) {
            this.trackRenderer = new TrackRenderer(map, this);
        } else {
            this.trackRenderer = null;
        }
        this.gates = []
        for (const index in this.track.waypoints) {
            const gate = this.track.waypoints[index]
            this.gates.push(new Gate(gate, new Date(this.contestant.gate_times[gate.name])))
        }
        this.startingLine = new Gate(this.track.starting_line, new Date(this.contestant.gate_times[this.track.waypoints[0].name]))
        this.startingLinePassingTimes = [];
        this.contestant.updateScore(0)
        this.contestant.updateLatestStatus("")
        this.scoreCalculator = new ScoreCalculator(this)
    }

    updateData(contestantTrack) {
        this.contestant.updateScore(contestantTrack.score)
        this.contestant.updateTrackState(contestantTrack.current_state)
        try {
            this.contestant.updateLatestStatus(contestantTrack.score_log.slice(-1)[0])
        } catch (e) {

        }
        this.contestant.scoreLog = contestantTrack.score_log
        this.contestant.scoreByGate = contestantTrack.score_per_gate
        this.contestant.updateCurrentLeg(contestantTrack.current_leg)
        this.contestant.updateLastGateAndTimeDifference(contestantTrack.last_gate, contestantTrack.last_gate_time_offset)
    }

    hideTrack() {
        if (this.trackRenderer) {
            this.trackRenderer.hideTrack()
        }
    }

    showTrack() {
        if (this.trackRenderer) {
            this.trackRenderer.showTrack()
        }
    }

    hideAnnotations() {
        if (this.trackRenderer) {
            this.trackRenderer.hideAnnotations()
        }
    }

    showAnnotations() {
        if (this.trackRenderer) {
            this.trackRenderer.showAnnotations()
        }
    }

    addAnnotation(latitude, longitude, message, icon) {
        if (this.trackRenderer) {
            this.trackRenderer.addAnnotation(latitude, longitude, message, icon)
        }
    }

    renderAnnotations(annotations) {
        if (this.trackRenderer) {
            this.trackRenderer.renderAnnotations(annotations)
        }
    }

    renderPositions(b) {
        if (this.trackRenderer) {
            this.trackRenderer.renderPositions(b)
        }
    }
}

export class ContestantTracks {
    constructor(map, startTime, finishTime, contestantList, track, updateScoreCallback) {
        this.updateScoreCallback = updateScoreCallback
        this.startTime = startTime;
        this.finishTime = finishTime;
        this.track = track;
        this.contestants = new ContestantList(contestantList, updateScoreCallback)
        this.map = map
        this.tracks = []
    }

    getTrackForContestant(contestantID) {
        const contestant = this.contestants.getContestantById(contestantID)
        let track = this.tracks.find((track) => track.contestant.id === contestantID)
        if (!track) {
            console.log("Created new track for " + contestant.displayString())
            track = new ContestantTrack(this.map, contestant, this.track, this.startTime, this.finishTime);
            this.tracks.push(track);
        }
        return track;
    }


    addData(positions, annotations, contestantTracks) {
        positions.map((contestantReport) => {
            let track = this.getTrackForContestant(contestantReport.contestant_id);
            if (track) {
                const positions = contestantReport.position_data.map((position) => {
                    return [position.latitude, position.longitude]
                })
                track.renderPositions(positions);
            }
        })
        annotations.map((annotationWrapper) => {
            let track = this.getTrackForContestant(annotationWrapper.contestant_id);
            if (track) {

                track.renderAnnotations(annotationWrapper.annotations);
            }
        })
        contestantTracks.map((contestantTrack) => {
            let track = this.getTrackForContestant(contestantTrack.contestant);
            track.updateData(contestantTrack)
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