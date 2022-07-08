import React, {Component} from "react";
import {getGate, getGateValue, getTrackValue} from "./actualScoreUtilities";


const aboutPrecisionFlying = (scorecard, route) => {
    const gateWidths = route.waypoints.map((waypoint) => {
        return waypoint.width
    })
    return <div>
        <h2>Precision flying</h2>
        <p>
            Precision flying is a flying competition where the user is tasked with crossing a set of gates at specific
            times and recognising provided pictures along the route. The only navigation tools available to the pilot is
            a paper map annotated with the prescribed route and the expected passing times for the gates.
        </p>
        <h3>Gate rules</h3>
        <p>
            Most gates gives a penalty of {getGateValue(scorecard, "tp", "penalty_per_second")} points for each
            second more
            than {getGateValue(scorecard, "tp", "graceperiod_before")}s early
            or {getGateValue(scorecard, "tp", "graceperiod_after")}s late. Missing the gate is a penalty
            of {getGateValue(scorecard, "tp", "missed_penalty")} points.
            A maximum of {getGateValue(scorecard, "tp", "maximum_penalty")} points are awarded for bad
            timing, and missing the procedure turn (if required)
            gives {getGateValue(scorecard, "tp", "missed_procedure_turn_penalty")} points.
        </p>
        <p>
            The width of the gates range between {Math.min(...gateWidths)} and {Math.max(...gateWidths)} NM.
        </p>
        <p>
            Crossing the extended starting line ({getGateValue(scorecard, "sp", "extended_gate_width")} NM wide)
            backwards gives a penalty
            of {getGateValue(scorecard, "sp", "bad_crossing_extended_gate_penalty")} points.
        </p>
        {route.takeoff_gates.length > 0 && getGateValue(scorecard, "to", "maximum_penalty") > 0 ?
            <p>
                The route has a takeoff gate. If this is passed before the takeoff time or more than one minute after
                the
                takeoff time a penalty
                of {getGateValue(scorecard, "to", "maximum_penalty")} points
                is applied.
            </p> : null}
        {route.landing_gates.length > 0 && getGateValue(scorecard, "ldg", "maximum_penalty") > 0 ?
            <p>
                The route has a landing gate. If this is not passed by the finish time for the contestant, a penalty
                of {getGateValue(scorecard, "ldg", "maximum_penalty")} points is applied.
            </p> : null}
        <h3>Track rules</h3>
        Backtracking during the route (defined as more
        than {getTrackValue(scorecard, "backtracking_bearing_difference")} degrees of track for more
        than {getTrackValue(scorecard, "backtracking_grace_time_seconds")} seconds) gives a penalty
        of {getTrackValue(scorecard, "backtracking_penalty")} points per
        occurrence{getTrackValue(scorecard, "backtracking_maximum_penalty") >= 0 ?
        <span> (with a maximum of {getTrackValue(scorecard, "backtracking_maximum_penalty")} points)</span> : null}.
    </div>
}
export default aboutPrecisionFlying