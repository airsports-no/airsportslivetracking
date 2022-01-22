import React, {Component} from "react";
import {getGateValue, getTrackValue} from "./actualScoreUtilities";

const aboutANR = (scorecard) => {
    return <div>
        <h2>Air navigation race (ANR)</h2>
        <p>
            Air navigation race is a flying competition type where the pilot is to keep the aircraft inside a predefined
            corridor and cross the start and finish lines at predefined times.
        </p>
        <p>
            For this ANR task the corridor width is {getTrackValue(scorecard, "corridor_width")} NM. Contestants
            are given a penalty
            of {getTrackValue(scorecard, "corridor_outside_penalty")} points for each second outside the
            corridor beyond the
            first {getTrackValue(scorecard, "corridor_grace_time")} seconds. {getTrackValue(scorecard, "corridor_maximum_penalty") >= 0 ?
            <span>A maximum of {getTrackValue(scorecard, "corridor_maximum_penalty")} points will be awarded per leg for being outside the corridor.</span> : null}
        </p>
        <p>
            Missing the starting point gives a penalty
            of {getGateValue(scorecard, "sp", "missed_penalty")}. Passing the checkpoint more
            than {getGateValue(scorecard, "sp", "graceperiod_before")} seconds early
            or {getGateValue(scorecard, "sp", "graceperiod_after")} seconds
            late gives {getGateValue(scorecard, "sp", "penalty_per_second")} points per additional
            second. The maximum score for being late or early at the gate
            is {getGateValue(scorecard, "sp", "maximum_timing_penalty")} points.
        </p>
        <p>
            Missing the finish point gives a penalty
            of {getGateValue(scorecard, "fp", "missed_penalty")}. Passing the checkpoint more
            than {getGateValue(scorecard, "fp", "graceperiod_before")} seconds early
            or {getGateValue(scorecard, "fp", "graceperiod_after")} seconds
            late gives {getGateValue(scorecard, "fp", "penalty_per_second")} points per additional
            second. The maximum score for being late or early at the gate
            is {getGateValue(scorecard, "fp", "maximum_timing_penalty")} points.

        </p>
    </div>
}

export default aboutANR