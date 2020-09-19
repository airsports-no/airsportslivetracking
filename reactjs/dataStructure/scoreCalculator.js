import {alongTrackDistance, crossTrackDistance, getBearing, getDistance, getHeadingDifference} from "./utilities"
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

const TrackingStateText = ["Tracking", "Backtracking", "Procedure turn", "Failed procedure turn", "Deviating", "Waiting...", "Finished"]

export class ScoreCalculator {
    constructor(contestantTrack) {
        this.contestantTrack = contestantTrack
        this.gateScore = 0
        this.trackScore = 0
        this.trackingState = TrackingStates.beforeStart
        this.scoredByGate = {}
        this.scoreLog = []
        this.currentProcedureTurnGate = null
        this.currentProcedureTurnDirections = []
        this.lastGate = 0
        this.lastBearing = null
        this.legLog = [this.contestantTrack.gates[0].name]
        this.outstandingGates = Array.from(this.contestantTrack.gates)

    }

    getTurningPointBeforeNow(index) {
        const gatesCrossed = this.contestantTrack.gates.filter((gate) => {
            return gate.isTurningPoint && (gate.hasBeenPassed() && gate.passingTime < this.contestantTrack.positions[index].deviceTime)
        })
        return gatesCrossed.length ? gatesCrossed.slice(-1)[0] : null
    }

    getTurningPointAfterNow(index) {
        const gatesNotCrossed = this.contestantTrack.gates.filter((gate) => {
            return gate.isTurningPoint && !(gate.hasBeenPassed() && gate.passingTime < this.contestantTrack.positions[index].deviceTime)
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
        // Check starting line
        if (!this.contestantTrack.startingLine.hasBeenPassed()) {
            let intersectionTime = this.getTimeOfIntersectLastPosition(this.contestantTrack.startingLine)
            if (intersectionTime) {
                console.log("Intersected gate " + this.contestantTrack.startingLine.name + " at time " + intersectionTime)
                this.contestantTrack.startingLine.passingTime = intersectionTime
                this.contestantTrack.startingLinePassingTimes.push(intersectionTime)
            }
        }

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
                    s = Math.min(100, Math.floor(absoluteDifference) * 2) + " points for passing gate " + gate.name + " off by " + Math.round(difference)
                    console.log(s)
                    this.scoreLog.push(s)
                } else {
                    s = "0 points for passing gate " + gate.name + " off by " + Math.round(difference)
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
        this.contestantTrack.contestant.updateLatestStatus(message)
        this.scoredByGate[gate.name] += score
        this.trackScore += score
    }

    guessCurrentLeg() {
        const currentPosition = this.contestantTrack.positions.slice(-1)[0]
        let minimumDistance = 999999999999999
        let currentBestGate = null
        let insideLegs = []
        const gates = this.contestantTrack.gates.filter((g) => {
            return g.isTurningPoint
        })
        for (let index = 1; index < gates.length; index++) {
            const previousGate = gates[index - 1]
            const nextGate = gates[index]
            if (nextGate.hasBeenPassed()) continue // We are definitely done with this leg
            const crossTrack = crossTrackDistance(previousGate.latitude, previousGate.longitude, nextGate.latitude, nextGate.longitude, currentPosition.latitude, currentPosition.longitude)
            const absoluteCrossTrack = Math.abs(crossTrack)
            const distanceFromStart = alongTrackDistance(previousGate.latitude, previousGate.longitude, currentPosition.latitude, currentPosition.longitude, crossTrack)
            const distanceFromFinish = alongTrackDistance(nextGate.latitude, nextGate.longitude, currentPosition.latitude, currentPosition.longitude, -crossTrack)
            // console.log("Distance to " + nextGate.name + ": " + crossTrack + ", fromStart: " + distanceFromStart + ", fromFinish: " + distanceFromFinish + ", legDistance: " + nextGate.distance)
            if (distanceFromFinish + distanceFromStart <= nextGate.distance * 1.05) {
                insideLegs.push({gate: nextGate, absoluteCrossTrack: absoluteCrossTrack})
                // console.log("Inside")
                // We are inside the leg
                // if (absoluteCrossTrack < minimumDistance) {
                //     minimumDistance = absoluteCrossTrack
                //     currentBestGate = nextGate
                // }
            }
        }
        return insideLegs.sort((a, b) => {
            if (a.absoluteCrossTrack > b.absoluteCrossTrack) return 1;
            if (a.absoluteCrossTrack < b.absoluteCrossTrack) return -1;
            return 0
        })
    }

    sortOutBestLeg(bestGuesses, bearing) {
        const insideLegDistance = 500

        let currentLeg = null
        let minimumDistance = null
        for (const guess of bestGuesses) {
            if (guess.absoluteCrossTrack < insideLegDistance && Math.abs(getHeadingDifference(bearing, guess.gate.bearing) < 60)) {
                currentLeg = guess.gate
                console.log("Choosing best leg because inside leg distance")
                break
            }
            if (!minimumDistance || guess.absoluteCrossTrack < minimumDistance) {
                minimumDistance = guess.absoluteCrossTrack
                currentLeg = guess.gate
            }
        }
        if (currentLeg)
            console.log("Choosing best leg " + currentLeg.name)
        return currentLeg
    }

    calculateCurrentLeg() {
        const gateRange = 2000
        const currentPositionIndex = this.contestantTrack.positions.length - 1
        if (currentPositionIndex === 0) return null
        const currentPosition = this.contestantTrack.positions[currentPositionIndex]
        const previousPosition = this.contestantTrack.positions[currentPositionIndex - 1]
        const nextGate = this.getTurningPointAfterNow(currentPositionIndex)
        let distanceToNextGate = 9999999999999999
        if (nextGate)
            distanceToNextGate = getDistance(currentPosition.latitude, currentPosition.longitude, nextGate.latitude, nextGate.longitude)
        const lastGate = this.getTurningPointBeforeNow(currentPositionIndex)
        let distanceToLastGate = 9999999999999
        if (lastGate)
            distanceToLastGate = getDistance(lastGate.latitude, lastGate.longitude, currentPosition.latitude, currentPosition.longitude)
        const bearing = getBearing(previousPosition.latitude, previousPosition.longitude, currentPosition.latitude, currentPosition.longitude)
        const bestGuesses = this.guessCurrentLeg()
        console.log(bestGuesses)

        if (nextGate)
            console.log("Next gate " + nextGate.name + " distance " + distanceToNextGate)
        if (lastGate)
            console.log("Last gate " + lastGate.name + " distance " + distanceToLastGate)
        const bestGuess = this.sortOutBestLeg(bestGuesses, bearing, distanceToNextGate)
        let currentLeg;
        if (bestGuess === nextGate) {
            currentLeg = nextGate
        } else {
            if (distanceToNextGate < gateRange) {
                currentLeg = nextGate
            } else if (distanceToLastGate < gateRange) {
                currentLeg = nextGate
            } else {
                currentLeg = bestGuess
            }
        }
        this.legLog.push(currentLeg)
        return currentLeg
    }

    anyGatePassed() {
        return this.contestantTrack.gates.filter((gate) => {
            gate.hasBeenPassed()
        }).length > 0
    }

    calculateTrackScore() {
        if (!this.contestantTrack.startingLine.hasBeenPassed() && !this.anyGatePassed()) {
            return
        }
        const lookBack = 2
        const finishIndex = this.contestantTrack.positions.length - 1
        let startIndex = Math.max(finishIndex - lookBack, 0)
        const currentLeg = this.calculateCurrentLeg()
        this.contestantTrack.contestant.updateCurrentLeg(currentLeg)
        const firstPosition = this.contestantTrack.positions[startIndex]
        const lastPosition = this.contestantTrack.positions[finishIndex]
        const lastGateFirst = this.getTurningPointBeforeNow(startIndex)
        const lastGateLast = this.getTurningPointBeforeNow(finishIndex)
        const nextGateLast = this.getTurningPointAfterNow(finishIndex)
        const nextGateFirst = this.getTurningPointAfterNow(startIndex)
        if (!nextGateFirst && nextGateLast)
            // Just before the starting gate
            this.updateTrackingState(TrackingStates.tracking)
        if (!nextGateLast) {
            // We have passed the finish gate
            this.updateTrackingState(TrackingStates.finished)
            return
        }
        // const nextGateFirst = this.getTurningPointAfterNow(startIndex)
        const bearing = getBearing(firstPosition.latitude, firstPosition.longitude, lastPosition.latitude, lastPosition.longitude)
        let bearingDifference
        if (currentLeg)
            bearingDifference = Math.abs(getHeadingDifference(bearing, currentLeg.bearing))
        else
            bearingDifference = Math.abs(getHeadingDifference(bearing, nextGateLast.bearing))
        if (lastGateLast && lastGateLast.isProcedureTurn && !lastGateFirst.isProcedureTurn && this.trackingState !== TrackingStates.failedProcedureTurn) {
            // We have just passed a gate with a procedure turn
            this.updateTrackingState(TrackingStates.procedureTurn)
            this.currentProcedureTurnGate = lastGateLast
        }
        if (this.trackingState === TrackingStates.procedureTurn) {
            if (this.lastBearing) {
                const turnDirection = getHeadingDifference(this.lastBearing, bearing) > 0 ? "cw" : "ccw"
                this.currentProcedureTurnDirections.push(turnDirection)
            }
            if (bearingDifference < 50) {
                this.updateTrackingState(TrackingStates.tracking)
                if (!this.currentProcedureTurnDirections.includes(this.currentProcedureTurnGate.turnDirection)) {
                    this.updateTrackingState(TrackingStates.failedProcedureTurn)
                    this.updateScore(nextGateLast, 200, "Incorrect procedure turn at " + this.currentProcedureTurnGate.name)
                }
            }
        } else {
            if (bearingDifference > 90) {
                if (this.trackingState === TrackingStates.tracking) {
                    this.updateTrackingState(TrackingStates.backtracking)
                    this.updateScore(nextGateLast, 200, "Backtracking more than 90° from the track at " + lastPosition.deviceTime)
                }
            }
            if (bearingDifference < 90) {
                this.updateTrackingState(TrackingStates.tracking)
            }
        }

        this.lastBearing = bearing

    }


    updateFinalScore() {
        this.checkIntersections()
        this.calculateGateScore()
        this.calculateTrackScore()
        this.contestantTrack.contestant.updateScore(this.getScore())
    }

    getScore() {
        return this.gateScore + this.trackScore
    }

}