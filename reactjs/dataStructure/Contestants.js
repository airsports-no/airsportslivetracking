import distinctColors from "distinct-colors";


export class Contestant {
    constructor(id, contestantNumber, registrationNumber, pilot, navigator, trackerName, colour, startTime, finishedByTime, plannedSpeed, gate_times, updateScoreCallback) {
        this.id = id
        this.contestantNumber = contestantNumber;
        this.registrationNumber = registrationNumber;
        this.pilot = pilot;
        this.navigator = navigator;
        this.trackerName = trackerName;
        this.colour = colour
        this.takeoffTime = startTime
        this.finishedByTime = finishedByTime
        this.plannedSpeed = plannedSpeed
        this.gate_times = gate_times
        this.score = 0
        this.latestStatus = ""
        this.trackState = "Waiting..."
        this.currentLeg = ""
        this.lastGate = ""
        this.lastGateTimeDifference = 0
        this.updateScoreCallback = updateScoreCallback
        this.scoreByGate = {}
    }


    getScoreByGate(gateName) {
        if (this.scoreByGate.hasOwnProperty(gateName)) {
            return this.scoreByGate[gateName]
        }
        return NaN
    }


    displayString() {
        return this.pilot
    }

    displayFull() {
        return "Contestant: " + this.contestantNumber + "<br/>Pilot: " + this.pilot + "<br/>Navigator: " + this.navigator + "<br/>Aeroplane: " + this.registrationNumber
    }

    updateScore(score) {
        if (this.score !== score) {
            this.score = score
            this.updateScoreCallback(this)
        }
    }

    updateTrackState(state) {
        if (this.trackState !== state) {
            this.trackState = state
            this.updateScoreCallback(this)
        }
    }

    updateCurrentLeg(gateName) {
        if (this.currentLeg !== gateName) {
            this.currentLeg = gateName
            this.updateScoreCallback(this)
        }
    }

    updateLatestStatus(status) {
        if (this.latestStatus !== status) {
            this.latestStatus = status
            // console.log("Updating current status: " + status)
            this.updateScoreCallback(this)
        }
    }

    updateLastGateAndTimeDifference(gateName, timeDifference) {
        if (this.lastGate !== gateName) {
            this.lastGate = gateName
            this.lastGateTimeDifference = timeDifference
            this.updateScoreCallback(this)
        }
    }

}

export class ContestantList {
    constructor(contestantList, updateScoreCallback) {
        this.colours = distinctColors({count: contestantList.length})
        this.contestants = this.loadContestants(contestantList, updateScoreCallback);
    }

    loadContestants(contestantList, updateScoreCallback) {
        return contestantList.map((data) => {
            return new Contestant(data.id, data.contestant_number, data.team.aeroplane.registration, data.team.pilot, data.team.navigator, data.traccar_device_name, this.colours.pop().hex(), new Date(data.takeoff_time), new Date(data.finished_by_time), data.ground_speed, data.gate_times, updateScoreCallback)
        })
    }

    getContestantById(contestantId) {
        return this.contestants.find((contestant) => contestant.id === contestantId)
    }

    getContestantForTracker(trackerName) {
        return this.contestants.find((contestant) => contestant.trackerName === trackerName)
    }

    getContestantForTrackerForTime(trackerName, atTime) {
        return this.contestants.find((contestant) => contestant.trackerName === trackerName && contestant.takeoffTime <= atTime <= contestant.finishedByTime)
    }


}