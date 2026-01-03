import { Scorecard, GateScoreRule } from "../types";

export function getTrackValue(scorecard: Scorecard, name: keyof Scorecard): any {
    return scorecard[name];
}

export function getGateInScorecard(scorecard: Scorecard, gateType: string): GateScoreRule | undefined {
    return scorecard.gatescore_set.find((gate) => gate.gate_type === gateType);
}

export function getGateValue(scorecard: Scorecard, gateType: string, name: keyof GateScoreRule): any {
    const gate = getGateInScorecard(scorecard, gateType);
    if (gate) {
        return gate[name];
    }
    return null;
}
