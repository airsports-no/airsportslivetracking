import contestants from "./contestants.json";
import distinctColors from "distinct-colors";


export class Contestant {
    constructor(id, contestantNumber, registrationNumber, pilot, navigator, trackerName, colour, startTime, finishedByTime, plannedSpeed) {
        this.id = id
        this.contestantNumber = contestantNumber;
        this.registrationNumber = registrationNumber;
        this.pilot = pilot;
        this.navigator = navigator;
        this.trackerName = trackerName;
        this.colour = colour
        this.startTime = startTime
        this.finishedByTime = finishedByTime
        this.plannedSpeed = plannedSpeed
        this.score = 0
    }
}

export class ContestantList {
    constructor(contestantList) {
        this.colours = distinctColors({count: contestantList.length})
        this.contestants = this.loadContestants(contestantList);
    }

    loadContestants(contestantList) {
        return contestantList.map((data) => {
            return new Contestant(data.id, data.contestant_number, data.team.aeroplane.registration, data.team.pilot, data.team.navigator, data.traccar_device_name, this.colours.pop().hex(), new Date(data.start_time), new Date(data.finished_by_time), data.ground_speed)
        })
    }

    getContestantForTracker(trackerName) {
        return this.contestants.find((contestant) => contestant.trackerName === trackerName)
    }

    getContestantForTrackerForTime(trackerName, atTime) {
        return this.contestants.find((contestant) => contestant.trackerName === trackerName && contestant.startTime <= atTime <= contestant.finishedByTime)
    }


}