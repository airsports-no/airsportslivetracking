import React, {Component} from "react";
import {getGate, getGateValue, getTrackValue} from "./actualScoreUtilities";


function gateText(gates, track, gateType) {
    return <p>
        {gateType} gives a penalty of {getGateValue(gates, gateType, "Penalty per second")} points for each second more
        than {getGateValue(gates, gateType, "Graceperiod before")}s early
        or {getGateValue(gates, gateType, "Graceperiod after")}s late. Missing the gate is a penalty
        of {getGateValue(gates, gateType, "Missed penalty")} points.
        A maximum of {getGateValue(gates, gateType, "Maximum timing penalty")} points are awarded for bad timing
        {gateType!=="Starting point" && gateType!=="Finish point"?<span>, and
                missing the procedure turn (if required) gives {getGateValue(gates, gateType, "Procedure turn penalty")} points</span>:null}.
        {gateType === "Starting point" ?
            <span> Crossing the extended starting line ({getGateValue(gates, gateType, "Extended gate width")} NM wide) backwards gives a penalty of {getGateValue(gates, gateType, "Bad crossing extended gate penalty")}</span> : null}
    </p>
}

const aboutPrecisionFlying = (actualRules) => {
    return <div>
        <h2>Precision flying</h2>
        <p>
            Precision flying is a flying competition where the user is tasked with crossing a set of gates at specific
            times and recognising provided pictures along the route. The only navigation tools available to the pilot is
            a paper map annotated with the prescribed route and the expected passing times for the gates.
        </p>
        <h3>Gate rules</h3>
        {gateText(actualRules.gates, actualRules.track, "Starting point")}
        {gateText(actualRules.gates, actualRules.track, "Turning point")}
        {gateText(actualRules.gates, actualRules.track, "Secret point")}
        {gateText(actualRules.gates, actualRules.track, "Finish point")}
        {getGate(actualRules.gates, "Takeoff gate") ? <p>
            The route has a takeoff gate. If this is passed before the takeoff time or more than one minute after the
            takeoff time a penalty of {getGateValue(actualRules.gates, "Takeoff gate", "Maximum timing penalty")} points
            is applied.
        </p> : null}
        {getGate(actualRules.gates, "Landing gate") ? <p>
            The route has a landing gate. If this is not passed by the finish time for the contestant, a penalty
            of {getGateValue(actualRules.gates, "Landing gate", "Maximum timing penalty")} points is applied.
        </p> : null}
        <h3>Track rules</h3>
        Backtracking during the route (defined as more
        than {getTrackValue(actualRules.track, "backtracking bearing difference")} degrees of track for more
        than {getTrackValue(actualRules.track, "backtracking grace time seconds")} seconds gives a penalty
        of {getTrackValue(actualRules.track, "backtracking penalty")} points per occurrence (with a maximum
        of {getTrackValue(actualRules.track, "backtracking maximum penalty")} points).
    </div>
}
export default aboutPrecisionFlying