import React from "react";
import {getGateValue, getTrackValue} from "./actualScoreUtilities";


const aboutAirsports = (scorecard, route) => {
    const gateWidths = route.waypoints.map((waypoint) => {
        return waypoint.width
    })
    return <div>
        <h2>Air Sports Race</h2>
        <p>
            Air Sports Race is a flying competition where the user is tasked with crossing a set of known and secret gates at specific
            times while at the same time remaining within the corridor and avoiding any prohibited and penalty zones
            along the way. The only navigation tools available to the pilot is
            a paper map annotated with the prescribed route and the expected passing times for the scorecard.
        </p>
        <p>
            The corridor width is between {Math.min(...gateWidths)} and {Math.max(...gateWidths)} NM.
            Contestants are given a penalty
            of {getTrackValue(scorecard, "corridor_outside_penalty")} points for each second outside the
            corridor beyond the
            first {getTrackValue(scorecard, "corridor_grace_time")} seconds. {getTrackValue(scorecard, "corridor_maximum_penalty") >= 0 ?
            <span>A maximum of {getTrackValue(scorecard, "corridor_maximum_penalty")} points will be awarded per leg for being outside the corridor.</span> : null}
        </p>
        <p>
            Prohibited zones give a once off penalty
            of {getTrackValue(scorecard, "prohibited_zone_penalty")} each time the contestant enters the zone.
            Penalty zones give {getTrackValue(scorecard, "penalty_zone_penalty_per_second")} points per second
            beyond the
            first {getTrackValue(scorecard, "penalty_zone_grace_time")} seconds. {getTrackValue(scorecard, "penalty_zone_maximum") >= 0 ?
            <span>Each zone gives a maximum
            penalty of {getTrackValue(scorecard, "penalty_zone_maximum")} points.</span> : null}
        </p>
        <h3>Gate rules</h3>
        <p>
            Regular scorecard gives a penalty of {getGateValue(scorecard, "tp", "penalty_per_second")} points for each
            second more
            than {getGateValue(scorecard, "tp", "graceperiod_before")}s early
            or {getGateValue(scorecard, "tp", "graceperiod_after")}s late. Missing the gate is a penalty
            of {getGateValue(scorecard, "tp", "missed_penalty")} points.

        </p>
        <p>
            Secret scorecard gives a penalty of {getGateValue(scorecard, "secret", "penalty_per_second")} points for each
            second more
            than {getGateValue(scorecard, "secret", "graceperiod_before")}s early
            or {getGateValue(scorecard, "secret", "graceperiod_after")}s late. Missing the gate is a penalty
            of {getGateValue(scorecard, "secret", "missed_penalty")} points.

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
export default aboutAirsports