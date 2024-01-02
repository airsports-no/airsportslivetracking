import React, {Component} from "react";

export default class GateCountdownTimer extends Component {
    render() {
        // Note that the seconds to planned crossing is negative before and positive after. We therefore play with 
        // signs to make it correct.
        return <div className={"gate-countdown-timer"}>
            <div
                className={"gate-remaining-seconds" + (this.props.secondsToPlannedCrossing >= 1 ? " gate-remaining-seconds-red" : "")}>
                {this.props.secondsToPlannedCrossing <= 0 ? -this.props.secondsToPlannedCrossing.toFixed(0) : this.props.secondsToPlannedCrossing.toFixed(0)}
            </div>
            <div className={"gate-countdown-label"}>COUNTDOWN SEC</div>
            <div className={"gate-estimated-crossing-offset"}>
                {this.props.crossingOffsetEstimate < 0 ? "-" : "+"}{Math.abs(this.props.crossingOffsetEstimate).toFixed(0)}s
            </div>
        </div>
    }
}