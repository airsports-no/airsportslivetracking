import {crossTrackDistance, getBearing, getHeadingDifference} from "./utilities"
import {fractionOfLeg, intersect} from "./lineUtilities";

const TrackingStates = {
    tracking: 0,
    backtracking: 1,
    procedureTurn: 2,
    failedProcedureTurn: 3,
    deviating: 4,
    beforeStart: 5,
    finished: 6
}

const TrackingStateText = ["Tracking", "Backtracking", "Procedure turn", "Failed procedure turn", "Deviating", "Starting", "Finished"]

export class ScoreCalculator {
    constructor(contestantTrack) {
        this.contestantTrack = contestantTrack
        this.gateScore = 0
        this.trackScore = 0
        this.trackingState = TrackingStates.beforeStart
        this.scoredByGate = {}
        this.scoreLog = []
        this.previousTrackIndex = 0
        this.lastGate = 0
        this.outstandingGates = Array.from(this.contestantTrack.gates)

    }

    getTurningpointbeforeNow(index) {
        const gatesCrossed = this.contestantTrack.gates.filter((gate) => {
            return gate.isTurningPoint && (gate.missed || gate.passingTime !== -1 && gate.passingTime < this.contestantTrack.positions[index].deviceTime)
        })
        return gatesCrossed.length ? gatesCrossed.slice(-1)[0] : null
    }

    getTurningPointAfterNow(index) {
        const gatesNotCrossed = this.contestantTrack.gates.filter((gate) => {
            return gate.isTurningPoint && !(gate.missed || gate.passingTime !== -1 && gate.passingTime < this.contestantTrack.positions[index].deviceTime)
        }).filter((gate) => {
            return gate.isTurningPoint
        })
        return gatesNotCrossed.length ? gatesNotCrossed[0] : null
    }

    getTimeOfIntersectLastPosition(gate) {
        if (this.contestantTrack.positions.length > 1) {
            let segment = this.contestantTrack.positions.slice(-2);
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
            let gate = this.outstandingGates[i]
            if (intersectionTime) {
                console.log("Intersected gate " + gate.name + " at time " + intersectionTime)
                gate.passingTime = intersectionTime
                crossedGate = true;
            }
            if (crossedGate) {
                if (gate.passingTime === -1) {
                    gate.missed = true
                    console.log("Missed gate " + this.outstandingGates[i].name)
                }
                this.outstandingGates.splice(i, 1);
            }
        }
        // if (crossedGate) {
        //     this.updateGateScore()
        //     this.contestant.updateScore(this.scoreCalculator.getScore())
        // }
    }


    calculateGateScore() {
        console.log("Updating gate score " + this.lastGate)
        let index = 0
        let finished = false
        this.contestantTrack.gates.slice(this.lastGate).forEach(gate => {
            if (finished) return
            this.scoredByGate[gate.name] = 0;
            let gateScore = 0
            let s = ""
            if (gate.missed) {
                index += 1
                console.log("100 points for missing gate " + gate.name)
                this.scoreLog.push("100 points for missing gate " + gate.name)
                gateScore = 100
                s = "Missed gate " + gate.name
            } else if (gate.passingTime !== -1) {
                index += 1
                const difference = (gate.passingTime - gate.expectedTime) / 1000;
                const absoluteDifference = Math.abs(difference)
                if (absoluteDifference > 2) {
                    gateScore = Math.min(100, Math.floor(absoluteDifference) * 2)
                    s = Math.min(100, Math.floor(absoluteDifference) * 2) + " points for passing gate " + gate.name + " off by " + difference
                    console.log(s)
                    this.scoreLog.push(s)
                } else {
                    s = "0 points for passing gate " + gate.name + " off by " + difference
                    console.log(s)
                    this.scoreLog.push(s)
                }
            } else {
                finished = true
            }
            if (!finished) {
                this.contestantTrack.contestant.updateLatestStatus(s)
                this.gateScore += gateScore
                this.scoredByGate[gate.name] += this.gateScore;
            }
        });
        this.lastGate += index
    }

    updateTrackingState(state) {
        console.log("Updating state " + TrackingStateText[state])
        if (this.trackingState !== state) {
            this.trackingState = state
            this.contestantTrack.contestant.updateTrackState(TrackingStateText[state])
        }
    }

    updateScore(gate, score, message) {
        console.log(message)
        this.scoreLog.push(message)
        this.scoredByGate[gate.name] += score
        this.trackScore += score
    }

    guessCurrentLeg() {
        const currentPosition = this.contestantTrack.positions.slice(-1)[0]
        let minimumDistance = 999999999999999
        let currentBestGate = null
        const gates = this.contestantTrack.gates.filter((g) => {
            return g.isTurningPoint
        })
        for (let index = 1; index < gates.length; index++) {
            const previousGate = gates[index - 1]
            const nextGate = gates[index]
            const crossTrack = crossTrackDistance(previousGate.latitude, previousGate.longitude, nextGate.latitude, nextGate.longitude, currentPosition.latitude, currentPosition.longitude)
            if (crossTrack < minimumDistance) {
                minimumDistance = crossTrack
                currentBestGate = nextGate
            }
        }
        return currentBestGate
    }

    calculateTrackScore() {
        const lookBack = 2
        let startIndex = Math.max(this.previousTrackIndex - lookBack, 0)
        let finishIndex = startIndex + lookBack
        while (finishIndex < this.contestantTrack.positions.length) {
            const firstPosition = this.contestantTrack.positions[startIndex]
            const lastPosition = this.contestantTrack.positions[finishIndex]
            const lastGateFirst = this.getTurningpointbeforeNow(startIndex)
            const lastGateLast = this.getTurningpointbeforeNow(finishIndex)
            const nextGateLast = this.getTurningPointAfterNow(finishIndex)
            const nextGateFirst = this.getTurningPointAfterNow(startIndex)
            if (!nextGateFirst && nextGateLast)
                this.updateTrackingState(TrackingStates.tracking)
            if (!nextGateLast) {
                // We have passed the finish point
                this.updateTrackingState(TrackingStates.finished)
                return
            }
            if (!lastGateLast) {
                // We have not passed the starting point, so no scoring
                startIndex += 1
                finishIndex += 1
                continue
            }
            // const nextGateFirst = this.getTurningPointAfterNow(startIndex)
            if (lastGateLast.isProcedureTurn && !lastGateFirst.isProcedureTurn) {
                this.updateTrackingState(TrackingStates.procedureTurn)
            }
            const bearing = getBearing(firstPosition.latitude, firstPosition.longitude, lastPosition.latitude, lastPosition.longitude)
            const bearingDifference = Math.abs(getHeadingDifference(bearing, nextGateLast.bearing))
            if (bearingDifference < 90) {
                this.updateTrackingState(TrackingStates.tracking)
            }
            if (this.trackingState === TrackingStates.procedureTurn) {
                const turnDirection = getHeadingDifference(bearing, nextGateLast.bearing) > 0 ? "cw" : "ccw"
                if (lastGateLast.turnDirection !== turnDirection) {
                    this.updateTrackingState(TrackingStates.failedProcedureTurn)
                    this.updateScore(nextGateLast, 200, "Incorrect procedure turn at " + lastPosition.deviceTime)
                }
            } else {
                if (bearingDifference > 90) {
                    if (this.trackingState === TrackingStates.tracking) {
                        this.updateTrackingState(TrackingStates.backtracking)
                        this.updateScore(nextGateLast, 200, "Backtracking more than 90° from the track at " + lastPosition.deviceTime)
                    }
                }
            }
            startIndex += 1
            finishIndex += 1
        }
        this.previousTrackIndex = Math.max(0, startIndex - 1)
    }


    updateFinalScore() {
        this.contestantTrack.contestant.updateCurrentLeg(this.guessCurrentLeg())
        this.checkIntersections()
        this.calculateGateScore()
        this.calculateTrackScore()
        this.contestantTrack.contestant.updateScore(this.getScore())
    }

    getScore() {
        return this.gateScore + this.trackScore
    }

}