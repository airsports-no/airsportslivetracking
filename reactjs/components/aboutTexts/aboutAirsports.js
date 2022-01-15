import React, {Component} from "react";
import {getGate, getGateValue, getTrackValue} from "./actualScoreUtilities";


function gateText(gates, track, gateType) {
    return <p>
        {gateType} gives a penalty of {getGateValue(gates, gateType, "Penalty per second")} points for each second more
        than {getGateValue(gates, gateType, "Graceperiod before")}s early
        or {getGateValue(gates, gateType, "Graceperiod after")}s late. Missing the gate is a penalty
        of {getGateValue(gates, gateType, "Missed penalty")} points.
        A maximum of {getGateValue(gates, gateType, "Maximum timing penalty")} points are awarded for bad timing
        {gateType !== "Starting point" && gateType !== "Finish point" ? <span>, and
                missing the procedure turn (if required) gives {getGateValue(gates, gateType, "Procedure turn penalty")} points</span> : null}.
        {gateType === "Starting point" ?
            <span> Crossing the extended starting line ({getGateValue(gates, gateType, "Extended gate width")} NM wide) backwards gives a penalty of {getGateValue(gates, gateType, "Bad crossing extended gate penalty")}</span> : null}
    </p>
}

const aboutAirsports = (actualRules, waypoints) => {
    const gates = actualRules.gates
    const gateWidths = waypoints.map((waypoint) => {
        return waypoint.width
    })
    return <div>
        <h2>Air Sports Race</h2>
        <p>
            Air Sports Race is a flying competition where the user is tasked with crossing a set of gates known and secret at specific
            times while at the same time remaining within the corridor and avoiding any prohibited and penalty zones
            along the way. The only navigation tools available to the pilot is
            a paper map annotated with the prescribed route and the expected passing times for the gates.
        </p>
        <p>
            The corridor width is between {Math.min(...gateWidths)} and {Math.max(...gateWidths)} NM.
            Contestants are given a penalty
            of {getTrackValue(actualRules.track, "corridor outside penalty")} points for each second outside the
            corridor beyond the
            first {getTrackValue(actualRules.track, "corridor grace time")} seconds. {getTrackValue(actualRules.track, "corridor maximum penalty") >= 0 ?
            <span>A maximum of {getTrackValue(actualRules.track, "corridor maximum penalty")} points will be awarded per leg for being outside the corridor.</span> : null}
        </p>
        <p>
            Prohibited zones give a once off penalty
            of {getTrackValue(actualRules.track, "prohibited zone penalty")} each time the contestant enters the zone.
            Penalty zones give {getTrackValue(actualRules.track, "penalty zone penalty per second")} points per second
            beyond the
            first {getTrackValue(actualRules.track, "penalty zone grace time")} seconds. {getTrackValue(actualRules.track, "penalty zone maximum") >= 0 ?
            <span>Each zone gives a maximum
            penalty of {getTrackValue(actualRules.track, "penalty zone maximum")} points.</span> : null}
        </p>
        <h3>Gate rules</h3>
        <p>
            Regular gates gives a penalty of {getGateValue(gates, "Turning point", "Penalty per second")} points for each
            second more
            than {getGateValue(gates, "Turning point", "Graceperiod before")}s early
            or {getGateValue(gates, "Turning point", "Graceperiod after")}s late. Missing the gate is a penalty
            of {getGateValue(gates, "Turning point", "Missed penalty")} points.

        </p>
        <p>
            Secret gates gives a penalty of {getGateValue(gates, "Secret point", "Penalty per second")} points for each
            second more
            than {getGateValue(gates, "Secret point", "Graceperiod before")}s early
            or {getGateValue(gates, "Secret point", "Graceperiod after")}s late. Missing the gate is a penalty
            of {getGateValue(gates, "Secret point", "Missed penalty")} points.

        </p>
        {getGate(waypoints, "Takeoff gate") && getGateValue(actualRules.gates, "Takeoff gate", "Maximum timing penalty") > 0 ?
            <p>
                The route has a takeoff gate. If this is passed before the takeoff time or more than one minute after
                the
                takeoff time a penalty
                of {getGateValue(actualRules.gates, "Takeoff gate", "Maximum timing penalty")} points
                is applied.
            </p> : null}
        {getGate(waypoints, "Landing gate") && getGateValue(actualRules.gates, "Landing gate", "Maximum timing penalty") > 0 ?
            <p>
                The route has a landing gate. If this is not passed by the finish time for the contestant, a penalty
                of {getGateValue(actualRules.gates, "Landing gate", "Maximum timing penalty")} points is applied.
            </p> : null}
        <h3>Track rules</h3>
        Backtracking during the route (defined as more
        than {getTrackValue(actualRules.track, "backtracking bearing difference")} degrees of track for more
        than {getTrackValue(actualRules.track, "backtracking grace time seconds")} seconds) gives a penalty
        of {getTrackValue(actualRules.track, "backtracking penalty")} points per
        occurrence{getTrackValue(actualRules.track, "backtracking maximum penalty") >= 0 ?
        <span> (with a maximum of {getTrackValue(actualRules.track, "backtracking maximum penalty")} points)</span> : null}.
    </div>
}
export default aboutAirsports