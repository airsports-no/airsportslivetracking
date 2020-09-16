export class ScoreCalculator {
    constructor(contestantTrack) {
        this.contestantTrack = contestantTrack
        this.gateScore = 0
        this.trackScore = 0
    }

    getGateScore() {
        console.log("Updating gate score")
        let score = 0;
        this.contestantTrack.gates.forEach(gate => {
            if (gate.missed) {
                console.log("100 points for missing gate " + gate.name)
                score += 100
            }
            if (gate.passingTime !== -1) {
                const difference = Math.abs(gate.passingTime - gate.expectedTime);
                if (difference > 2) {
                    score += Math.min(100, Math.floor(difference))
                    console.log(Math.min(100, Math.floor(difference)) + " points for passing gate " + gate.name)
                } else {
                    console.log("No penalty for passing gate " + gate.name + " in time")
                }
            }
        });
        return score
    }

    updateGateScore() {
        this.gateScore = this.getGateScore()
    }

    getScore() {
        return this.gateScore + this.trackScore
    }

}