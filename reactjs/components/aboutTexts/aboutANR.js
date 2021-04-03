import React, {Component} from "react";

const aboutANR = (trackOverride, gateOverrides) => {
    let startGate = null, finishGate = null
    for (const gate of gateOverrides) {
        if (gate.for_gate_types.includes("sp")) {
            startGate = <p>
                Missing the starting point gives a penalty of {gate.checkpoint_not_found}. Passing the checkpoint more
                than {gate.checkpoint_grace_period_before} seconds early or {gate.checkpoint_grace_period_after} seconds
                late gives {gate.checkpoint_penalty_per_second} points per additional
                second. {gate.checkpoint_maximum_penalty ?
                <span>The maximum scorer for being late or early at the gate is {gate.checkpoint_maximum_penalty}</span> : null}
            </p>
        }
        if (gate.for_gate_types.includes("fp")) {
            finishGate = <p>
                Missing the finish point gives a penalty of {gate.checkpoint_not_found}. Passing the checkpoint more
                than {gate.checkpoint_grace_period_before} seconds early or {gate.checkpoint_grace_period_after} seconds
                late gives {gate.checkpoint_penalty_per_second} points per additional
                second. {gate.checkpoint_maximum_penalty ?
                <span>The maximum scorer for being late or early at the gate is {gate.checkpoint_maximum_penalty}</span> : null}
            </p>
        }
    }


    return <div>
        <h2>Air navigation race (ANR)</h2>
        <p>
            Air navigation race is a flying competition type where the pilot is to keep the aircraft inside a predefined
            corridor and cross the start and finish lines at predefined times.
        </p>
        {trackOverride ? <p>
            For this ANR task the corridor width is {trackOverride.corridor_width} NM. Contestants are given a penalty
            of {trackOverride.corridor_outside_penalty} points for each second outside the corridor beyond the
            first {trackOverride.corridor_grace_time} seconds.
        </p> : null}
        {startGate}
        {finishGate}
    </div>
}

export default aboutANR