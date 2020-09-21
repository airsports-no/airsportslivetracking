import {alongTrackDistance, crossTrackDistance, getBearing, getDistance, getHeadingDifference} from "./utilities"
import {fractionOfLeg, intersect} from "./lineUtilities";
import {anomalyAnnotationIcon, informationAnnotationIcon} from "./iconDefinitions";

const Scorecard = {
    missedGate: 100,
    gateTimingPerSecond: 3,
    gatePerfectLimitSeconds: 2,
    maximumGateScore: 100,
    backtracking: 200,
    missedProcedureTurn: 200,
    belowMinimumAltitude: 500,
    takeoffTimeLimitSeconds: 60,
    missedTakeoffGate: 100
}

const TrackingStates = {
    tracking: 0,
    backtracking: 1,
    procedureTurn: 2,
    failedProcedureTurn: 3,
    deviating: 4,
    beforeStart: 5,
    finished: 6
}

const insideGates = {
    inside: 0,
    outside: 1
}

const TrackingStateText = ["Tracking", "Backtracking", "Procedure turn", "Failed procedure turn", "Deviating", "Waiting...", "Finished"]

export class ScoreCalculator {
    constructor(contestantTrack) {
        this.scorecard = Scorecard
        this.contestantTrack = contestantTrack
        this.score = 0
        this.trackingState = TrackingStates.beforeStart
        this.scoreByGate = {}
        this.scoreLog = []
        this.currentProcedureTurnGate = null
        this.currentProcedureTurnDirections = []
        this.lastGate = 0
        this.lastBearing = null
        this.currentSpeedEstimate = 0
        this.legLog = [this.contestantTrack.gates[0].name]
        this.outstandingGates = Array.from(this.contestantTrack.gates)
        this.previousGateDistances = null
        this.insideGates = null
    }

    calculateDistanceToOutstandingGates(currentPosition) {
        const gateDistances = this.outstandingGates.map((gate) => {
            return {
                distance: getDistance(currentPosition.latitude, currentPosition.longitude, gate.latitude, gate.longitude),
                gate: gate
            }
        })
        gateDistances.sort((a, b) => {
            if (a.distance > b.distance) return 1;
            if (a.distance < b.distance) return -1;
            return 0
        })
        return gateDistances
    }

    checkIfGateHasBeenMissed() {
        if (!this.contestantTrack.startingLine.hasBeenPassed()) {
            return
        }
        const currentPosition = this.contestantTrack.positions.slice(-1)[0]
        const distances = this.calculateDistanceToOutstandingGates(currentPosition)
        if (distances.length === 0) return
        if (!this.insideGates) {
            this.insideGates = {}
            distances.map((item) => {
                this.insideGates[item.gate.name] = false
            })
        }
        const insides = {}
        distances.map((item) => {
            insides[item.gate.name] = item.distance < item.gate.insideDistance || (item.distance < item.gate.outsideDistance && this.insideGates[item.gate.name])
        })
        let haveSeenInside = false
        for (const item of this.outstandingGates) {
            if (haveSeenInside) {
                insides[item.name] = false  // Only ever consider moving out of the first next gate
                this.insideGates[item.name] = false
            }
            if (this.insideGates[item.name] && !insides[item.name]) {
                // Have moved from inside to outside
                this.updateScore(item, 0, "Left the vicinity of gate " + item.name + " without passing it", currentPosition.latitude, currentPosition.longitude, anomalyAnnotationIcon)
                this.checkIntersections(item)
            }
            if (insides[item.name]) haveSeenInside = true

        }
        this.insideGates = insides
    }

    updateScore(gate, score, message, latitude, longitude, icon) {
        // console.log(message)
        this.scoreLog.push(message)
        this.contestantTrack.contestant.updateLatestStatus(message)
        this.contestantTrack.addAnnotation(latitude, longitude, message, icon)
        // Must be done before global score update, otherwise it will be counted twice.
        this.updateScoreByGate(gate.name, score)
        // Must be done after score by gate
        this.score += score
    }

    updateScoreByGate(gateName, score) {
        if (!this.scoreByGate.hasOwnProperty(gateName))
            this.scoreByGate[gateName] = this.score + score
        else
            this.scoreByGate[gateName] += score
    }

    getScoreByGate(gateName) {
        if (this.scoreByGate.hasOwnProperty(gateName)) {
            return this.scoreByGate[gateName]
        }
        return NaN
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

    missOutstandingGates() {
        let i = this.outstandingGates.length
        while (i--) {
            let gate = this.outstandingGates[i]
            gate.missed = true
            // console.log("Missed gate " + this.outstandingGates[i].name)
            this.outstandingGates.splice(i, 1);
        }

    }

    checkIntersections(forceGate) {
        // Check starting line
        if (!this.contestantTrack.startingLine.hasBeenPassed()) {
            let intersectionTime = this.getTimeOfIntersectLastPosition(this.contestantTrack.startingLine)
            if (intersectionTime) {
                // console.log("Intersected gate " + this.contestantTrack.startingLine.name + " at time " + intersectionTime)
                this.contestantTrack.startingLine.passingTime = intersectionTime
                this.contestantTrack.startingLinePassingTimes.push(intersectionTime)
            }
        }

        let i = this.outstandingGates.length
        let crossedGate = false
        while (i--) {
            const gate = this.outstandingGates[i]
            const intersectionTime = this.getTimeOfIntersectLastPosition(gate)
            if (intersectionTime) {
                // console.log("Intersected gate " + gate.name + " at time " + intersectionTime)
                gate.passingTime = intersectionTime
                crossedGate = true;
            }
            if (forceGate === gate) crossedGate = true
            if (crossedGate) {
                if (gate.passingTime === -1) {
                    gate.missed = true
                    // console.log("Missed gate " + this.outstandingGates[i].name)
                }
                this.outstandingGates.splice(i, 1);
            }
        }
    }


    calculateGateScore() {
        let index = 0
        let finished = false
        const currentPosition = this.contestantTrack.positions.slice(-1)[0]
        this.contestantTrack.gates.slice(this.lastGate).forEach(gate => {
            if (finished) return
            if (gate.missed) {
                index += 1
                const s = this.scorecard.missedGate + " points for missing gate " + gate.name
                this.updateScore(gate, this.scorecard.missedGate, s, currentPosition.latitude, currentPosition.longitude, anomalyAnnotationIcon)
                if (gate.isProcedureTurn) {
                    this.updateScore(gate, this.scorecard.missedProcedureTurn, this.scorecard.missedProcedureTurn + " for missing procedure turn at " + gate.name, gate.latitude, gate.longitude, anomalyAnnotationIcon)
                }
            } else if (gate.passingTime !== -1) {
                index += 1
                const difference = (gate.passingTime - gate.expectedTime) / 1000;
                const absoluteDifference = Math.abs(difference)
                if (absoluteDifference > this.scorecard.gatePerfectLimitSeconds) {
                    const gateScore = Math.min(this.scorecard.maximumGateScore, (Math.floor(absoluteDifference) - this.scorecard.gateTimingPerSecond) * this.scorecard.gateTimingPerSecond)
                    this.updateScore(gate, gateScore, gateScore + " points for passing gate " + gate.name + " off by " + Math.round(difference) + "s", currentPosition.latitude, currentPosition.longitude, informationAnnotationIcon)
                } else {
                    this.updateScore(gate, 0, 0 + " points for passing gate " + gate.name + " off by " + Math.round(difference) + "s", currentPosition.latitude, currentPosition.longitude, informationAnnotationIcon)
                }
            } else {
                finished = true
            }
        });
        this.lastGate += index
    }

    updateTrackingState(state) {
        // console.log("Updating state " + TrackingStateText[state])
        if (this.trackingState !== state) {
            this.trackingState = state
            this.contestantTrack.contestant.updateTrackState(TrackingStateText[state])
        }
    }


    guessCurrentLeg() {
        const currentPosition = this.contestantTrack.positions.slice(-1)[0]
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
                // console.log("Choosing best leg because inside leg distance")
                break
            }
            if (!minimumDistance || guess.absoluteCrossTrack < minimumDistance) {
                minimumDistance = guess.absoluteCrossTrack
                currentLeg = guess.gate
            }
        }
        if (currentLeg)
            // console.log("Choosing best leg " + currentLeg.name)
            return currentLeg
    }

    calculateCurrentLeg() {
        const gateRange = 4000
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
        const bestGuess = this.sortOutBestLeg(bestGuesses, bearing, distanceToNextGate)
        let currentLeg;
        if (bestGuess === nextGate) {
            currentLeg = nextGate
        } else {
            if (distanceToNextGate < gateRange) {
                currentLeg = nextGate
            } else if (distanceToLastGate < gateRange) {
                currentLeg = nextGate  // We only care about the next leg after we have passed one
            } else {
                currentLeg = bestGuess
            }
        }
        this.legLog.push(currentLeg)
        return currentLeg
    }

    anyGatePassed() {
        return this.contestantTrack.gates.filter((gate) => {
            return gate.hasBeenPassed()
        }).length > 0
    }

    allGatesPassed() {
        return this.contestantTrack.gates.filter((gate) => {
            return !gate.hasBeenPassed()
        }).length === 0
    }

    calculateTrackScore() {
        if (this.trackingState === TrackingStates.finished) return
        if (!this.contestantTrack.startingLine.hasBeenPassed() && !this.anyGatePassed()) {
            return
        }
        const finishIndex = this.contestantTrack.positions.length - 1
        const lastPosition = this.contestantTrack.positions[finishIndex]
        const speed = this.getSpeed()
        if ((speed === 0 || lastPosition.deviceTime > this.contestantTrack.contestant.finishedByTime) && !this.allGatesPassed()) {
            // Contestant has finished
            // console.log("Speed is zero or end time has been passed, assume contestant has finished")
            this.missOutstandingGates()
            this.updateTrackingState(TrackingStates.finished)
            return
        }

        const lookBack = 2
        let startIndex = Math.max(finishIndex - lookBack, 0)
        let currentLeg = this.calculateCurrentLeg()
        this.contestantTrack.contestant.updateCurrentLeg(currentLeg)
        const firstPosition = this.contestantTrack.positions[startIndex]
        const nextGateLast = this.getTurningPointAfterNow(finishIndex)
        if (!nextGateLast) {
            // We have passed the finish gate
            this.updateTrackingState(TrackingStates.finished)
            return
        }
        const lastGateFirst = this.getTurningPointBeforeNow(startIndex)
        const lastGateLast = this.getTurningPointBeforeNow(finishIndex)
        const bearing = getBearing(firstPosition.latitude, firstPosition.longitude, lastPosition.latitude, lastPosition.longitude)
        let bearingDifference
        if (currentLeg)
            bearingDifference = Math.abs(getHeadingDifference(bearing, currentLeg.bearing))
        else {
            bearingDifference = Math.abs(getHeadingDifference(bearing, nextGateLast.bearing))
            currentLeg = nextGateLast
        }
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
                    this.updateScore(nextGateLast, this.scorecard.missedProcedureTurn, this.scorecard.missedProcedureTurn + " points for incorrect procedure turn at " + this.currentProcedureTurnGate.name, lastPosition.latitude, lastPosition.longitude, anomalyAnnotationIcon)
                }
            }
        } else {
            if (bearingDifference > 90) {
                if (this.trackingState === TrackingStates.tracking) {
                    this.updateTrackingState(TrackingStates.backtracking)
                    this.updateScore(nextGateLast, this.scorecard.backtracking, this.scorecard.backtracking + " points for backtracking at " + currentLeg.name, lastPosition.latitude, lastPosition.longitude, anomalyAnnotationIcon)
                }
            }
            if (bearingDifference < 90) {
                this.updateTrackingState(TrackingStates.tracking)
            }
        }

        this.lastBearing = bearing

    }

    getSpeed() {
        const currentPositionIndex = this.contestantTrack.positions.length - 1
        if (currentPositionIndex === 0) return 0
        const currentPosition = this.contestantTrack.positions[currentPositionIndex]
        const previousPosition = this.contestantTrack.positions[currentPositionIndex - 1]

        this.currentSpeedEstimate = (getDistance(previousPosition.latitude, previousPosition.longitude, currentPosition.latitude, currentPosition.longitude) / 1852) / ((currentPosition.deviceTime - previousPosition.deviceTime) * 1000)
        return this.currentSpeedEstimate
    }

    updateFinalScore() {
        this.checkIfGateHasBeenMissed()
        this.checkIntersections()
        this.calculateGateScore()
        this.calculateTrackScore()
        this.contestantTrack.contestant.updateScore(this.getScore())
    }

    getScore() {
        return this.score
    }

}