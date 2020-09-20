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
        this.updateScoreCallback = updateScoreCallback
        this.scoreByGate = {}
    }

    displayString() {
        return this.pilot
    }

    displayFull() {
        return "Contestant: " +this.contestantNumber + "<br/>Pilot: " + this.pilot + "<br/>Navigator: " + this.navigator + "<br/>Aeroplane: " + this.registrationNumber
    }

    updateScore(score) {
        this.score = score
        this.updateScoreCallback(this)
    }

    updateTrackState(state) {
        this.trackState = state
        this.updateScoreCallback(this)
    }

    updateCurrentLeg(gate) {
        this.currentLeg = gate ? gate.name : ""
        this.updateScoreCallback(this)
    }

    updateLatestStatus(status) {
        this.latestStatus = status
        console.log("Updating current status: " + status)
        this.updateScoreCallback(this)
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

    getContestantForTracker(trackerName) {
        return this.contestants.find((contestant) => contestant.trackerName === trackerName)
    }

    getContestantForTrackerForTime(trackerName, atTime) {
        return this.contestants.find((contestant) => contestant.trackerName === trackerName && contestant.takeoffTime <= atTime <= contestant.finishedByTime)
    }


}