import React, {Component} from "react";
import {getGateValue, getTrackValue} from "./actualScoreUtilities";

const aboutANR = (actualRules) => {
    return <div>
        <h2>Air navigation race (ANR)</h2>
        <p>
            Air navigation race is a flying competition type where the pilot is to keep the aircraft inside a predefined
            corridor and cross the start and finish lines at predefined times.
        </p>
        <p>
            For this ANR task the corridor width is {getTrackValue(actualRules.track, "corridor width")} NM. Contestants
            are given a penalty
            of {getTrackValue(actualRules.track, "corridor outside penalty")} points for each second outside the
            corridor beyond the
            first {getTrackValue(actualRules.track, "corridor grace time")} seconds. {getTrackValue(actualRules.track, "corridor maximum penalty") >= 0 ?
            <span>A maximum of {getTrackValue(actualRules.track, "corridor maximum penalty")} points will be awarded per leg for being outside the corridor.</span> : null}
        </p>
        <p>
            Missing the starting point gives a penalty
            of {getGateValue(actualRules.gates, "Starting point", "Missed penalty")}. Passing the checkpoint more
            than {getGateValue(actualRules.gates, "Starting point", "Graceperiod before")} seconds early
            or {getGateValue(actualRules.gates, "Starting point", "Graceperiod after")} seconds
            late gives {getGateValue(actualRules.gates, "Starting point", "Penalty per second")} points per additional
            second. The maximum score for being late or early at the gate
            is {getGateValue(actualRules.gates, "Starting point", "Maximum timing penalty")} points.
        </p>
        <p>
            Missing the finish point gives a penalty
            of {getGateValue(actualRules.gates, "Finish point", "Missed penalty")}. Passing the checkpoint more
            than {getGateValue(actualRules.gates, "Finish point", "Graceperiod before")} seconds early
            or {getGateValue(actualRules.gates, "Finish point", "Graceperiod after")} seconds
            late gives {getGateValue(actualRules.gates, "Finish point", "Penalty per second")} points per additional
            second. The maximum score for being late or early at the gate
            is {getGateValue(actualRules.gates, "Finish point", "Maximum timing penalty")} points.

        </p>
    </div>
}

export default aboutANR